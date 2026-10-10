#!/usr/bin/env python3
"""Build V7 locally from official Google recovery, then prepare one 32 GB USB."""
import argparse,pathlib,subprocess,plistlib,sys,os,shutil,json,gzip,hashlib,datetime
R=pathlib.Path(__file__).resolve().parent
URL='https://dl.google.com/device/recovery/ruby-user/16452207/recovery.zip'
def run(*a,**kw):return subprocess.run([str(x) for x in a],check=True,**kw)
def sha(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def disk_info(disk):
 d=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',disk]))
 if not(d.get('WholeDisk') is True and d.get('Internal') is False and d.get('VirtualOrPhysical')=='Physical' and d.get('BusProtocol')=='USB' and d.get('Writable') is True and d.get('DeviceBlockSize')==512 and d.get('DeviceNode')==disk and 28*(1<<30)<=d.get('TotalSize',0)<=40*(1<<30)):
  raise ValueError('Requires an external physical USB whole disk, 28–40 GiB, writable, 512-byte sectors. Your 240 GB working SSD is refused.')
 return d

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--disk',required=True);p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--recovery-zip',type=pathlib.Path);a=p.parse_args()
 if sys.platform!='darwin':p.error('This wrapper runs on macOS only.')
 if os.geteuid()!=0:p.error('Run with sudo; the preparation VM needs access to the selected raw USB.')
 for n in ['qemu-system-x86_64','qemu-img','qemu-io','mcopy','mformat','lz4']:
  if not shutil.which(n):p.error('Missing '+n+'. Install with: brew install qemu mtools lz4')
 info=disk_info(a.disk);W=a.work.expanduser().resolve();W.mkdir(parents=True,exist_ok=True)
 if ',' in str(W) or ',' in str(R):raise ValueError('Kit/work paths cannot contain commas because of QEMU option parsing.')
 for name,h in json.loads((R/'asset-hashes.json').read_text()).items():
  if hashlib.sha256((R/name).read_bytes()).hexdigest()!=h:raise ValueError('Kit asset hash mismatch: '+name)
 if shutil.disk_usage(W).free<25*(1<<30) and not (W/'ruby-recovery.raw').exists():raise ValueError('Need about 25 GiB free in --work for the download, sparse extraction, and build. Use another mounted Mac drive if needed.')
 source=W/'source.qcow2';manifest=W/'source.qcow2.manifest.json'
 if source.exists():
  if not manifest.exists():raise ValueError('Incomplete prior build. Preserve logs, then use a new --work directory.')
  md=json.loads(manifest.read_text())
  if md.get('original_raw_sha256')!='4f4490415d4db0721fa99ad10abd64b1b05c284b6c0e413907da948561de8c9e' or sha(source)!=md['output_sha256'] or md.get('vendor',{}).get('policy_sha256')!='098aa91b65df24ff713d5ff0e8c2dd28c6c89224441eaef4398315645cb9cfb8':raise ValueError('Cached source validation failed; use a new --work directory.')
  base=pathlib.Path(json.loads(subprocess.check_output(['qemu-img','info','--output=json',str(source)]))['full-backing-filename'])
  if not base.is_file() or str(base).startswith('/dev/') or sha(base)!=md['original_raw_sha256']:raise ValueError('Cached official recovery backing file failed validation.')
 else:
  print('Building locally from Google. No USB writes yet. Keep this Terminal open. Build log: '+str(W/'assembly.log'),flush=True)
  cmd=[sys.executable,R/'source/assemble_native_android.py','--output',source,'--cache',W,'--assets',R/'assets','--format','qcow2']
  cmd+=['--recovery-zip',a.recovery_zip.resolve()] if a.recovery_zip else ['--download']
  with (W/'assembly.log').open('wb') as log:run(*cmd,stdout=log,stderr=subprocess.STDOUT)
 image=W/'installer.img'
 if not image.exists():
  with gzip.open(R/'installer.img.gz','rb') as src,image.open('xb') as dst:shutil.copyfileobj(src,dst,1<<20)
 virtual=json.loads(subprocess.check_output(['qemu-img','info','--output=json',str(source)]))['virtual-size']
 request=dict(usb_bytes=info['TotalSize'],source_bytes=virtual,official_recovery=URL,assembly_manifest=json.loads(manifest.read_text()))
 (W/'prepare-request.json').write_text(json.dumps(request,indent=2)+'\n')
 fat=W/'prepare-work.fat'
 with fat.open('wb') as f:f.truncate(512<<20)
 run('mformat','-i',fat,'-F','::')
 for name in ['installer.img','prepare-request.json']:run('mcopy','-i',fat,W/name,'::/')
 print('\nUSB selected: '+a.disk+' | '+str(info.get('MediaName'))+' | %.1f GB'%(info['TotalSize']/1e9))
 print('All contents of THIS USB will be erased. The working 240 GB Googlebook SSD and internal drives are not exposed to the VM.')
 token='ERASE '+a.disk
 if input('Type exactly '+token+' to prepare it (Enter cancels): ').strip()!=token:print('Cancelled. No USB writes.');return
 if disk_info(a.disk)!=info:raise ValueError('USB identity changed; refusing')
 run('diskutil','unmountDisk',a.disk);raw=a.disk.replace('/dev/disk','/dev/rdisk',1)
 cmd=['qemu-system-x86_64','-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-vga','none','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',R/'linux-kernel','-initrd',R/'initrd.gz','-append','rdinit=/init console=ttyS0,115200 loglevel=4 gbrunch.prepare_usb=1', '-drive',f'if=none,id=usb,format=raw,file={raw}','-device','virtio-blk-pci,drive=usb,serial=GBRUNCH_PREP_USB','-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work','-drive',f'if=none,id=source,format=qcow2,readonly=on,file={source}','-device','virtio-blk-pci,drive=source']
 with (W/'prepare-vm.log').open('wb') as log:
  try:run(*cmd,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
  finally:
   for name in ['prepare-log.txt','prepare-result.json','status.txt']:
    subprocess.run(['mcopy','-o','-i',str(fat),'::/'+name,str(W/name)])
 if (W/'status.txt').read_text().strip()!='0' or not json.loads((W/'prepare-result.json').read_text()).get('passed'):raise ValueError('USB preparation failed; preserve all files in '+str(W))
 run('diskutil','eject',a.disk)
 print('USB prepared and readback verified. Boot it on the HP with F9. Keep the original SSD disconnected. Reports: '+str(W))
if __name__=='__main__':main()
