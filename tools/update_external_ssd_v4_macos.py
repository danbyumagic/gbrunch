#!/usr/bin/env python3
"""Build locally from the selected SSD, back up and patch GBRUNCH/GBVENDOR only."""
import argparse,hashlib,json,math,os,pathlib,plistlib,re,subprocess,sys,zipfile
from maintain_external_ssd_macos import validate_disk_identity,sha256_file
GUIDS={'GBRUNCH':'4ab7c001-7400-4bab-b412-43cbd52b9fb1','GBVENDOR':'4ab7c002-7400-4bab-b412-43cbd52b9fb1'}
MiB=1<<20

def validate_targets(result,compat_bytes,vendor_bytes):
 parts=result['partitions'];by={p['name']:p for p in parts}
 assert len(by)==len(parts)
 spans=sorted((p['offset'],p['offset']+p['bytes']) for p in parts)
 assert all(x[1]<=y[0] for x,y in zip(spans,spans[1:]))
 for name,nbytes in [('GBRUNCH',compat_bytes),('GBVENDOR',vendor_bytes)]:
  p=by[name];assert p['guid']==GUIDS[name] and p['offset']%MiB==0
  assert 0<nbytes<=p['bytes'] and nbytes%512==0
 assert compat_bytes==by['GBRUNCH']['bytes']==64*MiB
 assert result['source_ssd_readonly'] is True and result['graphics_av_checks_passed'] is True
 return {name:by[name] for name in GUIDS}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--disk',required=True);p.add_argument('--qemu',required=True)
 p.add_argument('--mcopy',required=True);p.add_argument('--mformat',required=True)
 p.add_argument('--work',required=True,type=pathlib.Path)
 a=p.parse_args()
 if sys.platform!='darwin' or os.geteuid()!=0:p.error('Run on macOS with sudo.')
 if not re.fullmatch(r'/dev/disk[0-9]+',a.disk):p.error('Use an external whole disk, e.g. /dev/disk21.')
 def identity():
  meta=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',a.disk]));validate_disk_identity(meta,a.disk);return meta
 meta=identity();raw=a.disk.replace('/dev/disk','/dev/rdisk')
 assets=pathlib.Path(__file__).resolve().parent;manifest=json.loads((assets/'asset-hashes.json').read_text())
 for name,digest in manifest.items():
  if sha256_file(assets/name)!=digest:p.error('Asset mismatch: '+name)
 work=a.work.absolute()
 if work.exists() or work.is_symlink():p.error('Use a new work directory; keep previous backups/reports.')
 work.mkdir(parents=True);(work/'disk-identity.plist').write_bytes(plistlib.dumps(meta))
 state={'phase':'building','disk':a.disk,'writes_started':False};report_files=[]
 def run(*cmd,**kw):return subprocess.run([str(x) for x in cmd],check=True,**kw)
 def save():
  (work/'host-status.json').write_text(json.dumps(state,indent=2)+'\n')
 def read_range(name,offset,nbytes):
  dest=work/name
  assert offset%MiB==0 or offset==0
  run('dd','if='+raw,'of='+str(dest),'bs=1m','skip='+str(offset//MiB),'count='+str(math.ceil(nbytes/MiB)),stderr=subprocess.DEVNULL)
  with dest.open('r+b') as f:f.truncate(nbytes)
  return dest
 def check_same_disk(expected_gpt):
  again=identity()
  assert again['TotalSize']==meta['TotalSize'] and again.get('DeviceTreePath')==meta.get('DeviceTreePath'),'Disk identity changed'
  primary=read_range('current-primary-gpt.bin',0,17408)
  assert sha256_file(primary)==expected_gpt,'GPT changed during build; refusing writes'
 def write_image(image,target):
  run('dd','if='+str(image),'of='+raw,'bs=1m','seek='+str(target['offset']//MiB),'conv=notrunc')
  run('sync')
  got=read_range('verify-'+target['name']+'.bin',target['offset'],image.stat().st_size)
  assert sha256_file(got)==sha256_file(image),'Write verification failed: '+target['name']
  got.unlink()
 success=False
 try:
  save();fat=work/'work.fat'
  with fat.open('xb') as f:f.truncate(1<<30)
  run(a.mformat,'-i',fat,'-F','-T','2097152','::')
  (work/'GBRUNCH-BUILD-MARKER.txt').write_text('GBRUNCH local build-tool work disk\n')
  (work/'request.json').write_bytes((assets/'request.json').read_bytes())
  for name in ['GBRUNCH-BUILD-MARKER.txt','request.json']:run(a.mcopy,'-i',fat,work/name,'::/')
  run('diskutil','unmountDisk',a.disk)
  print('Building patched vendor from SSD, exposed READ-ONLY. No recovery download needed.',flush=True)
  cmd=[a.qemu,'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(assets/'linux-kernel'),'-initrd',str(assets/'initrd.gz'),'-append','rdinit=/init console=ttyS0,115200 loglevel=5 panic=0 gbrunch.toolvm=1 gbrunch.compat_update=1','-drive',f'if=none,id=work,format=raw,file={str(fat).replace(",",",,")}','-device','virtio-blk-pci,drive=work','-drive',f'if=none,id=disk,format=raw,file={raw},readonly=on','-device','virtio-blk-pci,drive=disk']
  with (work/'vm-console.txt').open('wb') as out:vm=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  for name in ['status.txt','build-log.txt','update-result.json','policy-changes.txt','policy-before.txt','policy-after.txt']:
   dest=work/name
   cp=subprocess.run([a.mcopy,'-i',str(fat),'::/'+name,str(dest)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   if cp.returncode==0:report_files.append(dest)
  assert vm.returncode==0 and (work/'status.txt').read_text().strip()=='0','Local vendor build failed; SSD unchanged'
  result=json.loads((work/'update-result.json').read_text());vendor=work/'vendor-local.erofs'
  run(a.mcopy,'-i',fat,'::/vendor.erofs',vendor)
  assert vendor.stat().st_size==result['vendor_bytes'] and sha256_file(vendor)==result['vendor_sha256']
  compat=assets/'gbrunch-compat-v4.ext4';targets=validate_targets(result,compat.stat().st_size,vendor.stat().st_size)
  check_same_disk(result['primary_gpt_sha256'])
  print('Build validated. Saving backups of GBRUNCH and GBVENDOR only.',flush=True)
  backups={}
  for name,target in targets.items():
   backups[name]=read_range('before-'+name+'.bin',target['offset'],target['bytes'])
  state.update(phase='backups saved',targets=targets,backup_hashes={n:sha256_file(v) for n,v in backups.items()});save();run('sync')
  check_same_disk(result['primary_gpt_sha256'])
  state.update(phase='writing GBVENDOR',writes_started=True);save()
  try:
   print('Writing and verifying GBVENDOR.',flush=True);write_image(vendor,targets['GBVENDOR'])
   state['phase']='writing GBRUNCH';save()
   print('Writing and verifying GBRUNCH.',flush=True);write_image(compat,targets['GBRUNCH'])
   check_same_disk(result['primary_gpt_sha256'])
  except Exception:
   state['phase']='restoring backups';save();check_same_disk(result['primary_gpt_sha256'])
   for name in ['GBVENDOR','GBRUNCH']:write_image(backups[name],targets[name])
   state['phase']='backups restored after failure';save();raise
  state.update(phase='complete',gpt_unchanged=True,userdata_untouched=True);save();success=True
 except Exception as exc:
  state['error']=repr(exc);save();print('Update failed:',exc,flush=True)
 finally:
  archive=work.with_name(work.name+'-reports.zip')
  with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
   for file in [work/'disk-identity.plist',work/'vm-console.txt',work/'host-status.json',*report_files]:
    if file.exists():z.write(file,file.name)
  if os.environ.get('SUDO_UID') and os.environ.get('SUDO_GID'):
   uid,gid=int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID'])
   for file in [work,*work.rglob('*'),archive]:os.chown(file,uid,gid)
  print('Report archive:',archive,flush=True)
 if not success:sys.exit('Preserve the work directory and backups. Do not assume the update succeeded.')
 print('Completed update. Keep the local backups; eject the SSD and boot the HP.',flush=True)
if __name__=='__main__':main()
