#!/usr/bin/env python3
"""Initialize ONLY unused space on the physical boot USB (64 GB or larger)."""
import sys,pathlib,subprocess,json,struct,zlib,uuid,hashlib,os,fcntl,traceback
sys.path.insert(0,'/opt/gbrunch/source')
from inspect_recovery import gpt
from dualboot_installer import identity,capacity,require
G=1<<30;M=1<<20;MAGIC='GBRUNCH toolbox v0.3'
def run(*a,**kw):return subprocess.run([str(x) for x in a],check=True,**kw)
def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
def parse(path):
 with open(path,'rb',buffering=0) as f:
  parts=gpt(f);f.seek(0);mbr=f.read(512);h=f.read(512);tlba,count,esz=struct.unpack_from('<QII',h,72)
  require(tlba==2 and count in (128,248) and esz==128,'Unsupported ISO GPT geometry')
  f.seek(tlba*512);table=f.read(count*esz);oldback=struct.unpack_from('<Q',h,32)[0];ts=(len(table)+511)//512;f.seek((oldback-ts)*512);tail=f.read((ts+1)*512)
 require(len(parts) in (2,3) and {p['index'] for p in parts}==set(range(1,len(parts)+1)),'Expected untouched toolbox ISO GPT')
 require(parts[0]['name']=='ISO9660' and parts[1]['name']=='Appended2' and (len(parts)==2 or parts[2]['name']=='Gap1'),'Unknown ISO partition profile')
 spans=sorted((p['offset'],p['offset']+p['bytes']) for p in parts)
 require(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])) and spans[-1][1]<=oldback*512,'Overlapping/out-of-range ISO partitions')
 require(mbr[510:]==b'\x55\xaa','Invalid MBR signature')
 require(any(mbr[446+i*16+4]==0xee for i in range(4)),'Expected protective GPT MBR')
 return dict(parts=parts,mbr=mbr,header=h,table=table,tail=tail,old_backup=oldback,table_sectors=ts,hash=hashlib.sha256(mbr+h+table+tail).hexdigest())
def make_plan(path,layout,meta):
 size=meta['bytes'];require(size>=55*G,'Requires a dedicated boot USB/USB SSD of at least 64 GB marketed capacity')
 offset=((layout['old_backup']*512+64*M+M-1)//M)*M;length=24*G
 require(offset+length+20*G<size,'Not enough space for workspace plus future trial area')
 slot=len(layout['parts']);require(not any(layout['table'][slot*128:(slot+1)*128]),'Next GPT slot is occupied')
 plan=dict(disk=meta,old_gpt_sha256=layout['hash'],workspace_offset=offset,workspace_bytes=length,workspace_guid=str(uuid.uuid4()),workspace_index=slot+1,future_trial_free_bytes=size-offset-length-(layout['table_sectors']+1)*512)
 plan['plan_sha256']=digest(plan);return plan
def tables(layout,plan):
 table=bytearray(layout['table']);ent=bytearray(128);ent[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le;ent[16:32]=uuid.UUID(plan['workspace_guid']).bytes_le;struct.pack_into('<QQQ',ent,32,plan['workspace_offset']//512,(plan['workspace_offset']+plan['workspace_bytes'])//512-1,0);n='GBWORK'.encode('utf-16le');ent[56:56+len(n)]=n;slot=plan['workspace_index']-1;table[slot*128:(slot+1)*128]=ent
 size=plan['disk']['bytes'];last=size//512-1;ts=layout['table_sectors'];h=bytearray(layout['header']);struct.pack_into('<Q',h,32,last);struct.pack_into('<Q',h,48,last-ts-1);struct.pack_into('<I',h,88,zlib.crc32(table));struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,last,1);struct.pack_into('<Q',bh,72,last-ts);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(layout['mbr'])
 for i in range(4):
  off=446+i*16
  if mbr[off+4]==0xee:struct.pack_into('<I',mbr,off+12,min(last,0xffffffff))
 return [(last*512,bh),((last-ts)*512,table),(1024,table),(512,h),(0,mbr)]
def main():
 require(os.geteuid()==0,'Run via sudo')
 medium=pathlib.Path('/run/live/medium');require((medium/'GBRUNCH-TOOLBOX.txt').read_text().strip()==MAGIC,'Not running from the GBRUNCH toolbox ISO')
 source=subprocess.check_output(['findmnt','-nr','-o','SOURCE','--target',str(medium)],text=True).strip();require(source.startswith('/dev/'),'Live medium must be a physical USB partition')
 node=pathlib.Path('/sys/class/block')/pathlib.Path(source).name;require((node/'partition').exists(),'Boot medium is not a disk partition')
 disk='/dev/'+node.resolve().parent.name;meta=identity(disk);require(meta['usb'],'Workspace setup is restricted to the boot USB')
 layout=parse(disk);plan=make_plan(disk,layout,meta)
 print('BOOT USB ONLY: '+disk+' | '+meta['serial']+' | %.1f GB'%(meta['bytes']/1e9))
 print('Preserve the existing ISO and EFI partitions.\nCreate a new 24 GiB persistent workspace in unused space.\nLeave %.1f GB unused for a future Googlebook trial.'%(plan['future_trial_free_bytes']/1e9))
 token='SETUP '+plan['plan_sha256'][:12]
 if input('Type '+token+' to apply, or Enter to cancel: ').strip()!=token:print('Cancelled. No USB writes.');return
 require(identity(disk)==meta and parse(disk)['hash']==plan['old_gpt_sha256'],'Boot USB identity/GPT changed')
 session=pathlib.Path('/run/gbrunch/setup');session.mkdir(parents=True,exist_ok=False)
 (session/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(session/'original-primary.bin').write_bytes(layout['mbr']+layout['header']+layout['table']);(session/'original-backup.bin').write_bytes(layout['tail'])
 loop=None;mounted=False;mount=pathlib.Path('/run/gbrunch/new-workspace');mount.mkdir(parents=True,exist_ok=True)
 with open(disk,'r+b',buffering=0) as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   loop=subprocess.check_output(['losetup','--find','--show','--offset',str(plan['workspace_offset']),'--sizelimit',str(plan['workspace_bytes']),disk],text=True).strip()
   require(capacity(loop)==plan['workspace_bytes'],'Loop size mismatch')
   run('mke2fs','-F','-t','ext4','-L','GBWORK','-m','0','-i','32768',loop)
   run('e2fsck','-f','-n',loop);run('mount','-t','ext4',loop,mount);mounted=True
   (mount/'persistence.conf').write_text('/ union\n')
   for name in ['recovery','reports','logs']:(mount/name).mkdir()
   shutil=__import__('shutil');shutil.copytree(session,mount/'setup-record')
   # Reports/cache belong to the normal live user; root-only operation records remain.
   for name in ['recovery','reports','logs']:os.chown(mount/name,1000,1000)
   os.sync();run('umount',mount);mounted=False;run('losetup','-d',loop);loop=None
   try:
    for offset,b in tables(layout,plan):f.seek(offset);require(f.write(b)==len(b),'Short GPT write');os.fsync(f.fileno())
    with open(disk,'rb') as check:parts=gpt(check)
    require(len(parts)==len(layout['parts'])+1 and parts[-1]['name']=='GBWORK','GPT readback failed')
    for p in layout['parts']:require(next(x for x in parts if x['index']==p['index'])==p,'Existing boot partition record changed')
   except Exception:
    for offset,b in [((layout['old_backup']-layout['table_sectors'])*512,layout['tail']),(1024,layout['table']),(512,layout['header']),(0,layout['mbr'])]:f.seek(offset);f.write(b);os.fsync(f.fileno())
    require(parse(disk)['hash']==layout['hash'],'GPT rollback verification failed');raise
  finally:
   if mounted:subprocess.run(['umount',str(mount)])
   if loop:subprocess.run(['losetup','-d',loop])
 print('Workspace created and GPT verified. Reboot into the normal desktop entry to enable persistence.')
if __name__=='__main__':
 rc=0
 try:main()
 except Exception:traceback.print_exc();rc=1
 input('Press Enter to close: ')
 sys.exit(rc)
