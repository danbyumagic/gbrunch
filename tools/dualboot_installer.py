#!/usr/bin/env python3
"""GBRUNCH experimental Linux installer: only validated GPT free space is writable.
Default operation is plan. Windows filesystems are never mounted or resized.
Source is V7 external SSD; Google bytes are copied locally, never distributed.
"""
import argparse,fcntl,hashlib,json,os,pathlib,re,stat,struct,subprocess,uuid,zlib,tempfile,shutil
from inspect_recovery import gpt
from googlebook_boot_menu import render as render_boot_menu
MiB=1<<20;GiB=1<<30
ESP='c12a7328-f81f-11d2-ba4b-00a0c93ec93b';BASIC='ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'
COMPAT_HASH='77cb6ec0e399a944a020b5d7d55d03dbd1bb5a2ba01012be91d315987ab69722'
SOURCE_GUIDS={'GBRUNCH':'4ab7c001-7400-4bab-b412-43cbd52b9fb1','GBVENDOR':'4ab7c002-7400-4bab-b412-43cbd52b9fb1','GBLOG':'4ab7c003-7400-4bab-b412-43cbd52b9fb1'}
EXPECTED={'userdata','KERN-A','super','KERN-B','ROOT-B','KERN-C','ROOT-C','OEM','ota_recovery_a','ota_recovery_b','EFI-SYSTEM','boot_a','boot_b','vbmeta_a','vbmeta_b','metadata','init_boot_a','init_boot_b','vendor_boot_a','vendor_boot_b','pvmfw_a','pvmfw_b','misc','RWFW-A','RWFW-B','recovery_a','recovery_b','desktop_security_persist','desktop_security_storage','frp_persist','GBRUNCH','GBVENDOR','GBLOG'}
def require(value,message):
 if not value:raise ValueError(message)
def sha_range(path,offset,size):
 h=hashlib.sha256()
 with open(path,'rb',buffering=0) as f:
  f.seek(offset)
  while size:
   b=f.read(min(size,4*MiB));require(bool(b),'Short read');h.update(b);size-=len(b)
 return h.hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def capacity(path):
 s=os.stat(path)
 if stat.S_ISREG(s.st_mode):return s.st_size
 with open(path,'rb',buffering=0) as f:return struct.unpack('Q',fcntl.ioctl(f,0x80081272,bytes(8)))[0]
def identity(path,fixture=False):
 p=pathlib.Path(path).resolve();s=p.stat()
 if fixture:
  require(stat.S_ISREG(s.st_mode),'Fixture mode accepts regular files only')
  return dict(path=str(p),bytes=s.st_size,inode=s.st_ino,device=s.st_dev,serial='FILE-FIXTURE')
 require(stat.S_ISBLK(s.st_mode),'A whole physical block disk is required')
 if p.name.startswith('loop'):return standalone_loop_identity(p,s)
 if p.name.startswith('nbd'):
  from toolbox_source import verify_nbd_identity
  return verify_nbd_identity(p,s)
 sys=pathlib.Path('/sys/class/block')/p.name;require(sys.exists() and not (sys/'partition').exists(),'Whole disk required')
 require(not p.name.startswith(('loop','ram','dm-','md')),'Virtual/mapped disks are not installer targets')
 with open(p,'rb') as f:require(struct.unpack('I',fcntl.ioctl(f,0x1268,bytes(4)))[0]==512,'512-byte sectors required')
 devpath=str(sys.resolve());serial=''
 for f in [sys/'device/serial',sys/'serial',sys/'device/wwid']:
  try:
   if f.exists():serial=f.read_text().strip();break
  except OSError:continue
 return dict(path=str(p),bytes=capacity(p),rdev=s.st_rdev,sysfs=devpath,serial=serial or 'NO-SERIAL',usb='/usb' in devpath)
def standalone_loop_identity(path,st):
 """A loop source is allowed only for the verified RO payload on our USB."""
 sys=pathlib.Path('/sys/class/block')/path.name
 backing=(sys/'loop/backing_file').read_text().strip()
 require(backing=='/payload/source.raw','Unrecognized loop backing file')
 source=pathlib.Path(backing);ss=source.stat();require(stat.S_ISREG(ss.st_mode),'Payload must be a regular file')
 rows=[r.split() for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines()]
 row=next((r for r in rows if r[4]=='/payload'),None)
 require(row is not None and 'ro' in row[5].split(',') and row[row.index('-')+1]=='ext4','Payload filesystem must be read-only ext4')
 node=pathlib.Path('/sys/dev/block')/row[2];node=node.resolve();require((node/'partition').exists(),'Payload must be on a USB partition')
 parent=identity('/dev/'+node.parent.name);require(parent['usb'],'Payload must be on USB media')
 marker=json.loads(pathlib.Path('/run/standalone-source-verified.json').read_text())
 manifest=pathlib.Path('/payload/SOURCE-MANIFEST.json');mh=hashlib.sha256(manifest.read_bytes()).hexdigest();md=json.loads(manifest.read_text())
 require(marker==dict(path=backing,inode=ss.st_ino,device=ss.st_dev,bytes=ss.st_size,sha256=md['source_sha256'],manifest_sha256=mh),'Payload verification record changed')
 with open(path,'rb') as f:require(struct.unpack('I',fcntl.ioctl(f,0x125e,bytes(4)))[0]==1,'Source loop must be read-only')
 require(capacity(path)==ss.st_size,'Loop must expose the complete source image')
 return dict(path=str(path),bytes=ss.st_size,rdev=st.st_rdev,sysfs=str(sys.resolve()),serial='USB-IMAGE:'+parent['serial'],usb=True,payload_identity=marker,parent_usb=parent)
def read_layout(path):
 with open(path,'rb',buffering=0) as f:
  parts=gpt(f);f.seek(0);mbr=f.read(512);header=f.read(512)
  tlba,count,esz=struct.unpack_from('<QII',header,72)
  require(tlba==2 and count==128 and esz==128,'Only standard 128-entry GPT is supported')
  backup=struct.unpack_from('<Q',header,32)[0];require((backup+1)*512==capacity(path),'GPT must already match disk size')
  f.seek(tlba*512);table=f.read(count*esz);f.seek((backup-32)*512);tail=f.read(33*512)
 require(mbr[510:]==b'\x55\xaa' and mbr[450]==0xee and all(mbr[446+i*16+4]==0 for i in [1,2,3]),'Protective GPT MBR required; hybrid MBR refused')
 spans=sorted((p['offset'],p['offset']+p['bytes']) for p in parts)
 require(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])),'Overlapping GPT partitions')
 first,last=struct.unpack_from('<QQ',header,40)
 require(all(first*512<=a<b<=(last+1)*512 for a,b in spans),'Partition outside usable GPT range')
 return dict(parts=parts,mbr=mbr,header=header,table=table,tail=tail,backup=backup,hash=hashlib.sha256(mbr+header+table+tail).hexdigest())
def unmounted(path):
 name=pathlib.Path(path).resolve().name;sys=pathlib.Path('/sys/class/block')/name
 nodes=[sys,*[p for p in sys.glob(name+'*') if (p/'partition').exists()]]
 ids={p.joinpath('dev').read_text().strip() for p in nodes if (p/'dev').exists()}
 for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():require(line.split()[2] not in ids,'Disk has mounted filesystems; refusing')
 for line in pathlib.Path('/proc/swaps').read_text().splitlines()[1:]:
  p=pathlib.Path(line.split()[0]);require(not (p.exists() and stat.S_ISBLK(p.stat().st_mode) and f'{os.major(p.stat().st_rdev)}:{os.minor(p.stat().st_rdev)}' in ids),'Disk has active swap')
 for node in nodes:require(not any((node/'holders').glob('*')),'Disk has active mapped/RAID holders')
def make_plan(source,target,userdata_gib=32,fixture=False):
 si=identity(source,fixture);ti=identity(target,fixture)
 require(si['path']!=ti['path'] and (fixture or si['rdev']!=ti['rdev']),'Source and destination are the same disk')
 if not fixture:
  require(si['usb'],'Source must be the external USB Googlebook SSD');require(not ti['usb'],'Destination must be an internal disk')
  unmounted(source);unmounted(target)
 require(userdata_gib in (16,32,48,64) or (fixture and userdata_gib==0),'Unsupported userdata size')
 sl=read_layout(source);tl=read_layout(target);by={p['name']:p for p in sl['parts']}
 require(set(by)==EXPECTED and len(by)==len(sl['parts']),'Source is not the known Ruby/GBRUNCH partition profile')
 for name,guid in SOURCE_GUIDS.items():require(by[name]['guid']==guid,'Unexpected source compatibility GUID')
 require(by['GBRUNCH']['bytes']==64*MiB,'Unexpected compatibility partition size')
 require(sha_range(source,by['GBRUNCH']['offset'],64*MiB)==COMPAT_HASH,'Source must contain the tested V7 compatibility image')
 require(not any(p['name'] in EXPECTED or p['name']=='GBRUNCH_EFI' for p in tl['parts']),'Destination already contains Googlebook partition names')
 require(any(p['type_guid']==ESP for p in tl['parts']),'Destination lacks a Windows EFI partition')
 windows=[]
 with open(target,'rb') as f:
  for p in tl['parts']:
   if p['type_guid']==BASIC:
    f.seek(p['offset']);boot=f.read(512)
    require(boot[3:11]!=b'-FVE-FS-','BitLocker volume detected; disable/decrypt it before installation')
    if boot[3:11]==b'NTFS    ':windows.append(p['guid'])
 require(bool(windows),'Destination must contain an identifiable NTFS Windows partition')
 used={p['index'] for p in tl['parts']};slots=[i for i in range(1,129) if i not in used]
 require(len(slots)>=len(sl['parts']),'Not enough free GPT entries')
 first,last=struct.unpack_from('<QQ',tl['header'],40);gaps=[];cursor=((first*512+MiB-1)//MiB)*MiB
 for p in sorted(tl['parts'],key=lambda p:p['offset']):
  if p['offset']>cursor:gaps.append((cursor,p['offset']))
  cursor=((p['offset']+p['bytes']+MiB-1)//MiB)*MiB
 if cursor<(last+1)*512:gaps.append((cursor,(last+1)*512))
 requested=[]
 for p in sorted(sl['parts'],key=lambda p:p['index']):
  size=(64*MiB if fixture and userdata_gib==0 else userdata_gib*GiB) if p['name']=='userdata' else p['bytes']
  requested.append((p,((size+MiB-1)//MiB)*MiB))
 total=sum(size for _,size in requested)
 gap=next(((a,b) for a,b in gaps if b-a>=total),None);require(gap is not None,f'Need one unallocated extent of {total/GiB:.2f} GiB. Shrink Windows first; this installer does not resize NTFS.')
 cursor=gap[0];new=[]
 for slot,(p,size) in zip(slots,requested):
  new.append(dict(index=slot,name='GBRUNCH_EFI' if p['name']=='EFI-SYSTEM' else p['name'],source_name=p['name'],offset=cursor,bytes=size,source_offset=p['offset'],source_bytes=p['bytes'],guid=str(uuid.uuid4()),type_guid=p['type_guid'],attributes=p['attributes']));cursor+=size
 value=dict(version=1,source=si,target=ti,source_gpt_sha256=sl['hash'],target_gpt_sha256=tl['hash'],source_compat_sha256=COMPAT_HASH,existing_partitions=tl['parts'],new_partitions=new,allocation_start=gap[0],allocation_end=cursor,required_bytes=total,userdata_gib=userdata_gib,fixture=fixture,windows_guids=windows,userdata='fresh; external Android data is preserved, not migrated',boot_order='new GBRUNCH entry appended; existing Windows priority is retained')
 value['plan_sha256']=digest(value);return value

def gpt_payload(layout,new):
 table=bytearray(layout['table'])
 for p in new:
  off=(p['index']-1)*128;require(not any(table[off:off+128]),'Planned GPT slot is occupied')
  ent=bytearray(128);ent[:16]=uuid.UUID(p['type_guid']).bytes_le;ent[16:32]=uuid.UUID(p['guid']).bytes_le;struct.pack_into('<QQQ',ent,32,p['offset']//512,(p['offset']+p['bytes'])//512-1,p['attributes']);n=p['name'].encode('utf-16le');require(len(n)<=72,'Partition name too long');ent[56:56+len(n)]=n;table[off:off+128]=ent
 header=bytearray(layout['header']);struct.pack_into('<I',header,88,zlib.crc32(table));struct.pack_into('<I',header,16,0);struct.pack_into('<I',header,16,zlib.crc32(header[:92]))
 backup=bytearray(header);struct.pack_into('<QQ',backup,24,layout['backup'],1);struct.pack_into('<Q',backup,72,layout['backup']-32);struct.pack_into('<I',backup,16,0);struct.pack_into('<I',backup,16,zlib.crc32(backup[:92]));return bytes(table),bytes(header),bytes(backup)
def validate_plan_layout(plan,source_layout,target_layout):
 existing=target_layout['parts'];old_guids={p['guid'] for p in existing};old_indices={p['index'] for p in existing};by={p['name']:p for p in source_layout['parts']};new=plan['new_partitions']
 require(len(new)==len(by) and {p['source_name'] for p in new}==set(by),'Plan does not cover the source profile')
 require(len({p['index'] for p in new})==len(new) and len({p['guid'] for p in new})==len(new),'Duplicate new GPT entries')
 first,last=struct.unpack_from('<QQ',target_layout['header'],40)
 spans=[]
 for p in new:
  original=by[p['source_name']]
  require(1<=p['index']<=128 and p['index'] not in old_indices and p['guid'] not in old_guids,'Plan collides with existing GPT entries')
  uuid.UUID(p['guid'])
  require(p['source_offset']==original['offset'] and p['source_bytes']==original['bytes'] and p['type_guid']==original['type_guid'] and p['attributes']==original['attributes'],'Source partition mapping changed')
  require(p['name']==('GBRUNCH_EFI' if original['name']=='EFI-SYSTEM' else original['name']),'Unexpected destination partition name')
  expected=(64*MiB if plan['fixture'] and plan['userdata_gib']==0 else plan['userdata_gib']*GiB) if p['name']=='userdata' else ((original['bytes']+MiB-1)//MiB)*MiB
  require(p['bytes']==expected and p['offset']%MiB==0,'Unexpected new extent size/alignment')
  a,b=p['offset'],p['offset']+p['bytes'];require(first*512<=a<b<=(last+1)*512,'Plan outside GPT usable space')
  require(all(b<=x['offset'] or a>=x['offset']+x['bytes'] for x in existing),'Plan overlaps an existing Windows partition')
  spans.append((a,b))
 spans.sort();require(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])),'New extents overlap')
 require(plan['existing_partitions']==existing,'Existing GPT entries changed')
 require(plan['userdata_gib'] in (16,32,48,64) or (plan['fixture'] and plan['userdata_gib']==0),'Unsupported userdata allocation')

def command(log,name,*args):
 with (log/(name+'.txt')).open('wb') as f:r=subprocess.run([str(x) for x in args],stdout=f,stderr=subprocess.STDOUT)
 require(r.returncode==0,f'{name} failed; see installer log')
def save(log,name,value):
 p=log/name;p.write_text(json.dumps(value,indent=2)+'\n')
 with p.open('rb') as f:os.fsync(f.fileno())
 os.sync()
def write_all(fd,data,offset):
 while data:
  n=os.pwrite(fd,data,offset);require(n>0,'Short write');data=data[n:];offset+=n
class Writer:
 def __init__(self,fd,plan):self.fd=fd;self.parts=plan['new_partitions']
 def write(self,offset,data):
  require(any(p['offset']<=offset and offset+len(data)<=p['offset']+p['bytes'] for p in self.parts),'Write escaped planned free-space partitions')
  write_all(self.fd,data,offset)
def prepare_payloads(plan,log,assets):
 source=plan['source']['path'];by={p['source_name']:p for p in plan['new_partitions']};efi=by['EFI-SYSTEM'];scratch=pathlib.Path(tempfile.mkdtemp(prefix='gbrunch-payload-'));fat=scratch/'target-efi.fat'
 with open(source,'rb') as f,open(fat,'wb') as o:f.seek(efi['source_offset']);o.write(f.read(efi['source_bytes']))
 if not plan['fixture']:
  kernel=subprocess.check_output(['mcopy','-i',str(fat),'::/EFI/GBRUNCH/kernel','-'],stderr=subprocess.DEVNULL)
  require(hashlib.sha256(kernel).hexdigest()=='7816c5d5b3500093e597b7362ecab103d5a32141b100d3eb7a8b33221fce7f41','Source does not contain the tested Google kernel')
 cfg=subprocess.check_output(['mcopy','-i',str(fat),'::/EFI/GBRUNCH/grub.cfg','-'],stderr=None).decode()
 matches=re.findall(r'^\s*linux\s+/EFI/GBRUNCH/kernel\s+(.+)$',cfg,re.M);require(len(matches)==1,'Source EFI must have one known Android kernel command line')
 cmd=matches[0];require('androidboot.init_rc=/oem/init.gbrunch.rc' in cmd,'Not a GBRUNCH boot configuration')
 old=next(p for p in read_layout(source)['parts'] if p['name']=='boot_a')['guid'];new=by['boot_a']['guid'];require('androidboot.boot_part_uuid='+old in cmd,'Source boot UUID does not match source GPT')
 cmd=cmd.replace('androidboot.boot_part_uuid='+old,'androidboot.boot_part_uuid='+new)
 require(assets.joinpath('internal-BOOTX64.EFI').is_file(),'Internal GRUB loader asset missing')
 # Separate FAT label and a separate EFI partition; Windows ESP never receives writes.
 command(log,'efi-label','mlabel','-i',fat,'-N',uuid.uuid4().hex[:8],'::GBRUNCH_INT')
 out=log/'target-grub.cfg';out.write_text(render_boot_menu(cmd))
 command(log,'efi-config','mcopy','-o','-i',fat,out,'::/EFI/GBRUNCH/grub.cfg')
 command(log,'efi-loader','mcopy','-o','-i',fat,assets/'internal-BOOTX64.EFI','::/EFI/BOOT/BOOTX64.EFI')
 command(log,'efi-fsck','fsck.fat','-n',fat)
 fresh=scratch/'target-log.fat'
 with fresh.open('wb') as f:f.truncate(by['GBLOG']['bytes'])
 args=['mformat','-i',fresh,'-v','GBRUNCH_LOG']
 if by['GBLOG']['bytes']>=64*MiB:args+=['-F']
 command(log,'log-format',*args,'::')
 return {'EFI-SYSTEM':fat,'GBLOG':fresh}
def apply_plan(plan,log,assets,confirmation,fixture=False,fault=None):
 check=dict(plan);h=check.pop('plan_sha256');require(digest(check)==h,'Plan checksum mismatch')
 require(plan['fixture']==fixture,'Fixture/live mode mismatch')
 require(confirmation=='INSTALL '+h[:12],'Explicit plan confirmation does not match')
 require(not log.exists(),'Use a new log directory');log.mkdir(parents=True)
 save(log,'plan.json',plan)
 source=plan['source']['path'];target=plan['target']['path']
 require(identity(source,fixture)==plan['source'] and identity(target,fixture)==plan['target'],'Disk identity changed')
 if not fixture:unmounted(source);unmounted(target)
 sl=read_layout(source);tl=read_layout(target)
 require(sl['hash']==plan['source_gpt_sha256'] and tl['hash']==plan['target_gpt_sha256'],'GPT changed since inspection')
 validate_plan_layout(plan,sl,tl)
 require(sha_range(source,next(p['offset'] for p in sl['parts'] if p['name']=='GBRUNCH'),64*MiB)==COMPAT_HASH,'Source V7 changed')
 (log/'original-primary.bin').write_bytes(tl['mbr']+tl['header']+tl['table']);(log/'original-backup.bin').write_bytes(tl['tail']);os.sync()
 state=dict(phase='preparing boot files',gpt_committed=False,windows_partitions_untouched=True,source_readonly=True);save(log,'status.json',state)
 try:payloads=prepare_payloads(plan,log,assets)
 except Exception as exc:
  state.update(phase='failed before installation writes',error=repr(exc));save(log,'status.json',state);raise
 state=dict(phase='writing unallocated space',gpt_committed=False,windows_partitions_untouched=True,source_readonly=True);save(log,'status.json',state)
 src=os.open(source,os.O_RDONLY);dst=os.open(target,os.O_RDWR);writer=Writer(dst,plan);gpt_started=False
 try:
  require(identity(source,fixture)==plan['source'] and identity(target,fixture)==plan['target'],'Disk identity changed before writes')
  if not fixture:
   fcntl.ioctl(src,0x125d,struct.pack('I',1))
   require(struct.unpack('I',fcntl.ioctl(src,0x125e,bytes(4)))[0]==1,'Could not protect source read-only')
  fcntl.flock(dst,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for p in plan['new_partitions']:
   if p['source_name']=='userdata':continue
   print('Copying and verifying '+p['name'],flush=True)
   local=payloads.get(p['source_name']);size=local.stat().st_size if local else p['source_bytes'];fd=os.open(local,os.O_RDONLY) if local else src;offset=0 if local else p['source_offset'];h=hashlib.sha256()
   try:
    for pos in range(0,size,4*MiB):
     b=os.pread(fd,min(4*MiB,size-pos),offset+pos);require(bool(b),'Source short read');h.update(b);writer.write(p['offset']+pos,b)
   finally:
    if local:os.close(fd)
   os.fsync(dst);require(sha_range(target,p['offset'],size)==h.hexdigest(),'Copy readback failed: '+p['name'])
   state['last_verified_partition']=p['name'];save(log,'status.json',state)
   if fault=='copy':raise RuntimeError('Injected copy failure')
  user=next(p for p in plan['new_partitions'] if p['name']=='userdata')
  # Bounded loop device exposes only the newly allocated userdata extent.
  loop=subprocess.check_output(['losetup','--find','--show','--offset',str(user['offset']),'--sizelimit',str(user['bytes']),target],text=True).strip()
  try:
   features='none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity'
   command(log,'userdata-format','mke2fs','-F','-t','ext4','-b','4096','-I','512','-i','16384','-m','0','-O',features,'-E','encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard','-J','size='+('4' if fixture else '64'),'-M','/data',loop)
   command(log,'userdata-fsck','e2fsck','-fn',loop)
  finally:subprocess.run(['losetup','-d',loop],check=True)
  require(identity(source,fixture)==plan['source'] and identity(target,fixture)==plan['target'],'Disk identity changed during copy')
  require(read_layout(source)['hash']==plan['source_gpt_sha256'],'Source GPT changed during copy')
  require(read_layout(target)['hash']==plan['target_gpt_sha256'],'Destination GPT changed during copy')
  table,header,backup=gpt_payload(tl,plan['new_partitions']);state['phase']='committing GPT';save(log,'status.json',state);gpt_started=True
  write_all(dst,table,(tl['backup']-32)*512);write_all(dst,backup,tl['backup']*512);os.fsync(dst)
  if fault=='gpt':raise RuntimeError('Injected GPT commit failure')
  write_all(dst,table,1024);write_all(dst,header,512);os.fsync(dst)
  got=read_layout(target);existing={p['index']:p for p in got['parts']}
  for p in plan['existing_partitions']:require(existing[p['index']]==p,'Existing Windows GPT entry changed')
  state.update(phase='installed; boot registration pending',gpt_committed=True);save(log,'status.json',state)
 except Exception as exc:
  if gpt_started:
   write_all(dst,tl['tail'],(tl['backup']-32)*512);write_all(dst,tl['mbr']+tl['header']+tl['table'],0);os.fsync(dst)
   require(read_layout(target)['hash']==tl['hash'],'GPT rollback verification failed')
  state.update(phase='failed; original GPT retained/restored',error=repr(exc),gpt_committed=False);save(log,'status.json',state);raise
 finally:
  os.close(src);os.close(dst)
  shutil.rmtree(next(iter(payloads.values())).parent)
 # Partition reread/UEFI registration is a separate step, never a reason to undo a complete copy.
 if not fixture:
  with open(target,'rb') as f:
   try:fcntl.ioctl(f,0x125f)
   except OSError as exc:state['partition_reread_warning']=repr(exc)
  try:
   before=subprocess.check_output(['efibootmgr','-v'],text=True);(log/'uefi-before.txt').write_text(before)
   ep=next(p for p in plan['new_partitions'] if p['source_name']=='EFI-SYSTEM')
   command(log,'uefi-create','efibootmgr','--create-only','--disk',target,'--part',ep['index'],'--label','GBRUNCH','--loader',r'\EFI\BOOT\BOOTX64.EFI')
   created=subprocess.check_output(['efibootmgr','-v'],text=True)
   order=lambda s:re.search(r'^BootOrder:\s*(.*)$',s,re.M).group(1).strip() if re.search(r'^BootOrder:',s,re.M) else None
   ids=lambda s:set(re.findall(r'^Boot([0-9A-Fa-f]{4})[ *]',s,re.M))
   added=ids(created)-ids(before);require(len(added)==1,'Could not identify newly created UEFI entry')
   old_order=order(before);require(bool(old_order),'Existing Windows boot order is unavailable')
   new_order=old_order+','+next(iter(added))
   try:
    command(log,'uefi-append','efibootmgr','--bootorder',new_order)
    after=subprocess.check_output(['efibootmgr','-v'],text=True);require(order(after)==new_order,'UEFI boot order verification failed')
   except Exception:
    command(log,'uefi-order-restore','efibootmgr','--bootorder',old_order);raise
   (log/'uefi-after.txt').write_text(after)
   state['uefi_entry_created']=True
  except Exception as exc:state['uefi_registration_error']=repr(exc);state['uefi_entry_created']=False
 state['phase']='complete';state['source_gpt_unchanged']=read_layout(source)['hash']==plan['source_gpt_sha256'];save(log,'status.json',state);return state

def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--source',required=True);a.add_argument('--target',required=True);a.add_argument('--userdata-gib',type=int,default=32);a.add_argument('--plan',type=pathlib.Path,required=True);a.add_argument('--apply',action='store_true');a.add_argument('--confirm');a.add_argument('--logs',type=pathlib.Path);a.add_argument('--assets',type=pathlib.Path,default=pathlib.Path('/installer'));a.add_argument('--fixture',action='store_true',help=argparse.SUPPRESS);args=a.parse_args()
 if args.apply:
  require(args.logs is not None and args.confirm is not None,'Apply requires logs and exact confirmation');plan=json.loads(args.plan.read_text());require(str(pathlib.Path(args.source).resolve())==plan['source']['path'] and str(pathlib.Path(args.target).resolve())==plan['target']['path'],'Requested disks differ from saved plan');print(json.dumps(apply_plan(plan,args.logs,args.assets,args.confirm,args.fixture),indent=2))
 else:
  require(not args.plan.exists(),'Refusing to overwrite a plan');plan=make_plan(args.source,args.target,args.userdata_gib,args.fixture);args.plan.write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2));print('To apply this exact plan, confirmation is INSTALL '+plan['plan_sha256'][:12])
if __name__=='__main__':main()
