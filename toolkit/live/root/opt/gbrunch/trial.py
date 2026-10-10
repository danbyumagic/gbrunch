#!/usr/bin/env python3
"""Deploy the verified local build ONLY into the boot USB's reserved tail."""
import pathlib,sys,subprocess,json,struct,zlib,uuid,os,fcntl,datetime,shutil,traceback
sys.path.insert(0,'/opt/gbrunch/source')
from dualboot_installer import require,identity,capacity,read_layout,sha_range,digest,Writer,prepare_payloads,command,write_all,validate_plan_layout
from inspect_recovery import gpt
from toolbox_source import local_source,workspace
M=1<<20;G=1<<30
def layout(path):
 with open(path,'rb') as f:
  parts=gpt(f);f.seek(0);mbr=f.read(512);header=f.read(512);tlba,count,esz=struct.unpack_from('<QII',header,72)
  require(tlba==2 and esz==128 and count in (128,248),'Unsupported toolbox GPT')
  f.seek(tlba*512);table=f.read(count*esz);backup=struct.unpack_from('<Q',header,32)[0];ts=(len(table)+511)//512
  require((backup+1)*512==capacity(path),'Initialize USB storage and reboot first')
  f.seek((backup-ts)*512);tail=f.read((ts+1)*512)
 require(len(parts)==4 and [p['name'] for p in parts]==['ISO9660','Appended2','Gap1','GBWORK'],'Requires a toolbox USB with workspace and no existing trial')
 return dict(parts=parts,mbr=mbr,header=header,table=table,backup=backup,ts=ts,tail=tail,hash=__import__('hashlib').sha256(mbr+header+table+tail).hexdigest())
def plan_trial(source,target):
 si=identity(source);ti=identity(target);require(si['usb'] and ti['usb'],'Source and boot USB must be verified USB objects')
 old=layout(target);sl=read_layout(source);cursor=(max(p['offset']+p['bytes'] for p in old['parts'])+M-1)//M*M
 last=struct.unpack_from('<Q',old['header'],48)[0];new=[]
 for i,p in enumerate(sorted(sl['parts'],key=lambda p:p['index']),5):
  size=16*G if p['name']=='userdata' else (p['bytes']+M-1)//M*M
  require(not any(old['table'][(i-1)*128:i*128]),'Trial GPT slot occupied')
  new.append(dict(index=i,name='GBRUNCH_EFI' if p['name']=='EFI-SYSTEM' else p['name'],source_name=p['name'],source_offset=p['offset'],source_bytes=p['bytes'],offset=cursor,bytes=size,guid=str(uuid.uuid4()),type_guid=p['type_guid'],attributes=p['attributes']));cursor+=size
 require(cursor<=(last+1)*512,'USB tail is too small for the trial and fresh 16 GiB Android data')
 value=dict(source=si,target=ti,source_gpt_sha256=sl['hash'],target_gpt_sha256=old['hash'],existing_partitions=old['parts'],new_partitions=new,userdata_gib=16,fixture=False,required_bytes=cursor-new[0]['offset'])
 value['plan_sha256']=digest(value);return value,old
def commit_payload(old,new):
 table=bytearray(old['table'])
 for p in new:
  e=bytearray(128);e[:16]=uuid.UUID(p['type_guid']).bytes_le;e[16:32]=uuid.UUID(p['guid']).bytes_le;struct.pack_into('<QQQ',e,32,p['offset']//512,(p['offset']+p['bytes'])//512-1,p['attributes']);name=p['name'].encode('utf-16le');e[56:56+len(name)]=name;off=(p['index']-1)*128;require(not any(table[off:off+128]),'Occupied GPT slot');table[off:off+128]=e
 h=bytearray(old['header']);struct.pack_into('<I',h,88,zlib.crc32(table));struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,old['backup'],1);struct.pack_into('<Q',bh,72,old['backup']-old['ts']);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));return table,h,bh
def apply_trial(plan,old,log,confirmation,assets):
 value=dict(plan);token=value.pop('plan_sha256');require(digest(value)==token and confirmation=='TRY '+token[:12],'Confirmation/plan mismatch')
 source=plan['source']['path'];target=plan['target']['path']
 require(identity(source)==plan['source'] and identity(target)==plan['target'],'Source/boot USB identity changed')
 require(layout(target)['hash']==old['hash'] and read_layout(source)['hash']==plan['source_gpt_sha256'],'GPT changed before copying')
 validate_plan_layout(plan,read_layout(source),old)
 log.mkdir(parents=True,exist_ok=False);(log/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(log/'original-primary.bin').write_bytes(old['mbr']+old['header']+old['table']);(log/'original-backup.bin').write_bytes(old['tail']);os.sync()
 state=dict(phase='preparing files',gpt_committed=False)
 def save():
  (log/'status.json').write_text(json.dumps(state,indent=2)+'\n');os.sync()
 save();payloads=prepare_payloads(plan,log,assets)
 try:
  fat=payloads['EFI-SYSTEM'];command(log,'trial-efi-label','mlabel','-i',fat,'::GBTRIAL_EFI')
  require((assets/'trial-BOOTX64.EFI').is_file(),'Trial EFI loader asset missing')
  command(log,'trial-efi-loader','mcopy','-o','-i',fat,assets/'trial-BOOTX64.EFI','::/EFI/BOOT/BOOTX64.EFI')
  # Retain the original HP/QEMU hardware gate and verbose Android command line.
  cfg=subprocess.check_output(['mcopy','-i',str(fat),'::/EFI/GBRUNCH/grub.cfg','-'],text=True)
  original_efi=next(p for p in read_layout(source)['parts'] if p['name']=='EFI-SYSTEM')
  sourcefat=log/'source-efi.fat'
  with open(source,'rb') as f,sourcefat.open('wb') as out:f.seek(original_efi['offset']);out.write(f.read(original_efi['bytes']))
  cfg=subprocess.check_output(['mcopy','-i',str(sourcefat),'::/EFI/GBRUNCH/grub.cfg','-'],text=True);sourcefat.unlink()
  oldguid=next(p['guid'] for p in read_layout(source)['parts'] if p['name']=='boot_a');newguid=next(p['guid'] for p in plan['new_partitions'] if p['source_name']=='boot_a')
  require('androidboot.boot_part_uuid='+oldguid in cfg,'Missing known boot UUID');cfg=cfg.replace('androidboot.boot_part_uuid='+oldguid,'androidboot.boot_part_uuid='+newguid)
  config=log/'trial-grub.cfg';config.write_text(cfg);command(log,'trial-config','mcopy','-o','-i',fat,config,'::/EFI/GBRUNCH/grub.cfg');command(log,'trial-efi-fsck','fsck.fat','-n',fat)
  src=os.open(source,os.O_RDONLY);dst=os.open(target,os.O_RDWR);started=False
  try:
   fcntl.flock(dst,fcntl.LOCK_EX|fcntl.LOCK_NB);writer=Writer(dst,plan)
   require(layout(target)['hash']==old['hash'],'Boot USB GPT changed')
   state['phase']='copying reserved USB tail';save()
   for p in plan['new_partitions']:
    if p['source_name']=='userdata':continue
    print('Copying and verifying '+p['name'],flush=True)
    local=payloads.get(p['source_name']);fd=os.open(local,os.O_RDONLY) if local else src;offset=0 if local else p['source_offset'];size=local.stat().st_size if local else p['source_bytes']
    try:
     for pos in range(0,size,4*M):
      b=os.pread(fd,min(4*M,size-pos),offset+pos);require(len(b)==min(4*M,size-pos),'Source short read');writer.write(p['offset']+pos,b)
     os.fsync(dst);require(sha_range(target,p['offset'],size)==sha_range(local or source,offset,size),'Trial copy readback failed')
    finally:
     if local:os.close(fd)
    state['last_verified_partition']=p['name'];save()
   p=next(p for p in plan['new_partitions'] if p['source_name']=='userdata')
   loop=subprocess.check_output(['losetup','--find','--show','--offset',str(p['offset']),'--sizelimit',str(p['bytes']),target],text=True).strip()
   try:
    require(capacity(loop)==p['bytes'],'Userdata extent mismatch')
    features='none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity'
    command(log,'trial-userdata-format','mke2fs','-F','-t','ext4','-b','4096','-I','512','-i','16384','-m','0','-O',features,'-E','encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard','-J','size=64','-M','/data',loop)
    command(log,'trial-userdata-fsck','e2fsck','-fn',loop)
   finally:subprocess.run(['losetup','-d',loop],check=True)
   require(identity(source)==plan['source'] and identity(target)==plan['target'],'Source/target identity changed during copy')
   require(layout(target)['hash']==old['hash'],'Boot USB GPT changed during copy')
   table,h,bh=commit_payload(old,plan['new_partitions']);started=True
   for offset,data in [((old['backup']-old['ts'])*512,table),(old['backup']*512,bh),(1024,table),(512,h)]:write_all(dst,data,offset);os.fsync(dst)
   with open(target,'rb') as f:parts=gpt(f)
   require(len(parts)==4+len(plan['new_partitions']),'GPT readback count mismatch')
   for p in old['parts']:require(next(x for x in parts if x['index']==p['index'])==p,'Toolbox/workspace GPT entry changed')
   state.update(phase='complete; reboot required',gpt_committed=True,toolbox_and_workspace_preserved=True);save()
  except Exception as exc:
   if started:
    write_all(dst,old['tail'],(old['backup']-old['ts'])*512);write_all(dst,old['mbr']+old['header']+old['table'],0);os.fsync(dst);require(layout(target)['hash']==old['hash'],'GPT rollback failed')
   state.update(phase='failed; trial not enabled',error=repr(exc),gpt_committed=False);save();raise
  finally:os.close(src);os.close(dst)
 finally:shutil.rmtree(next(iter(payloads.values())).parent)
 print('Trial prepared and verified. Reboot; select Try Googlebook from the toolbox boot menu.',flush=True)
def main():
 require(os.geteuid()==0,'Run via sudo')
 with local_source() as (source,w,parent):
  plan,old=plan_trial(source,parent['path']);print('BOOT USB ONLY: '+parent['path']+' | '+parent['serial']);print('Preserve the Linux toolbox, workspace and recovery cache. Create a separate Googlebook trial with fresh 16 GiB Android data. No internal disk writes.')
  print('Logs: '+str(w/'logs'));token='TRY '+plan['plan_sha256'][:12]
  answer=input('Type '+token+' to apply, or Enter to cancel: ').strip()
  if answer!=token:print('Cancelled; no trial writes.');return
  log=w/'logs'/('trial-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S'))
  apply_trial(plan,old,log,answer,pathlib.Path('/opt/gbrunch/source'))
if __name__=='__main__':
 rc=0
 try:main()
 except Exception:traceback.print_exc();rc=1
 input('Press Enter to close: ');sys.exit(rc)
