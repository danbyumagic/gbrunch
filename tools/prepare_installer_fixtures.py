#!/usr/bin/env python3
"""Private sparse fixtures. They contain dummy Windows/OS data, not Google images."""
import pathlib,uuid,struct,zlib,json,subprocess,os,shutil
from dualboot_installer import SOURCE_GUIDS,EXPECTED,ESP,BASIC,MiB
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/dualboot-installer';W=pathlib.Path('/tmp/gbrunch-installer-test');W.mkdir(exist_ok=True);L=R/'tools/local';e=os.environ.copy();e['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*a,**kw):return subprocess.run([str(x) for x in a],env=e,check=True,**kw)
def make(path,parts,size):
 sectors=size//512;table=bytearray(16384)
 for p in parts:
  ent=bytearray(128);ent[:16]=uuid.UUID(p['type_guid']).bytes_le;ent[16:32]=uuid.UUID(p['guid']).bytes_le;struct.pack_into('<QQQ',ent,32,p['offset']//512,(p['offset']+p['bytes'])//512-1,p.get('attributes',0));n=p['name'].encode('utf-16le');ent[56:56+len(n)]=n;table[(p['index']-1)*128:p['index']*128]=ent
 h=bytearray(512);h[:8]=b'EFI PART';struct.pack_into('<IIII',h,8,0x10000,92,0,0);struct.pack_into('<QQQQ',h,24,1,sectors-1,34,sectors-34);h[56:72]=uuid.uuid4().bytes_le;struct.pack_into('<QIII',h,72,2,128,128,zlib.crc32(table));struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,sectors-1,1);struct.pack_into('<Q',bh,72,sectors-33);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(512);mbr[450]=0xee;struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
 with path.open('wb') as f:
  f.truncate(size)
  for off,data in [(0,mbr),(512,h),(1024,table),((sectors-33)*512,table),((sectors-1)*512,bh)]:f.seek(off);f.write(data)
def populate(path,offset,file):
 with path.open('r+b') as dst,pathlib.Path(file).open('rb') as src:
  for pos in range(0,pathlib.Path(file).stat().st_size,MiB):
   b=src.read(MiB)
   if b.strip(b'\0'):dst.seek(offset+pos);dst.write(b)
source=W/'source.raw';parts=[];cursor=MiB;names=['userdata',*sorted(EXPECTED-{'userdata'})]
for i,n in enumerate(names,1):
 size={'userdata':64*MiB,'GBRUNCH':64*MiB,'EFI-SYSTEM':64*MiB,'GBLOG':8*MiB}.get(n,MiB)
 parts.append(dict(index=i,name=n,offset=cursor,bytes=size,type_guid=ESP if n=='EFI-SYSTEM' else '0fc63daf-8483-4772-8e79-3d69d8477de4',guid=SOURCE_GUIDS.get(n,str(uuid.uuid5(uuid.NAMESPACE_DNS,'fixture-'+n))),attributes=0));cursor+=size
make(source,parts,256*MiB);by={p['name']:p for p in parts}
populate(source,by['GBRUNCH']['offset'],R/'build/compat-wifi-v7/compat.ext4')
fat=W/'fixture-efi.fat'
with fat.open('wb') as f:f.truncate(64*MiB)
run(L/'usr/bin/mformat','-i',fat,'-F','-v','SOURCE_EFI','::');run(L/'usr/bin/mmd','-i',fat,'::/EFI','::/EFI/BOOT','::/EFI/GBRUNCH')
cfg=W/'fixture-grub.cfg';cfg.write_text("menuentry 'fixture only' {\n linux /EFI/GBRUNCH/kernel rdinit=/init console=ttyS0,115200 loglevel=4 gbrunch.installed_probe=1 androidboot.init_rc=/oem/init.gbrunch.rc androidboot.boot_part_uuid="+by['boot_a']['guid']+"\n initrd /EFI/GBRUNCH/initrd.gz\n}\n")
for p,n in [(B/'linux-kernel','kernel'),(B/'initrd.gz','initrd.gz'),(cfg,'grub.cfg')]:run(L/'usr/bin/mcopy','-i',fat,p,'::/EFI/GBRUNCH/'+n)
populate(source,by['EFI-SYSTEM']['offset'],fat);fat.unlink()
with source.open('r+b') as f:
 for p in parts:
  if p['name'] not in ['GBRUNCH','EFI-SYSTEM']:f.seek(p['offset']);f.write(('source-fixture-'+p['name']).encode())
windows=W/'windows-original.raw';wp=[];cursor=MiB
for i,(n,size,t) in enumerate([('Windows ESP',4*MiB,ESP),('Microsoft reserved',MiB,'e3c9e316-0b5c-4db8-817d-f92df00215ae'),('Windows C',8*MiB,BASIC),('Windows recovery',8*MiB,'de94bba4-06d1-4d40-a16a-bfd50179d6ac')],1):
 wp.append(dict(index=i,name=n,offset=cursor,bytes=size,type_guid=t,guid=str(uuid.uuid4())));cursor+=size
make(windows,wp,512*MiB)
with windows.open('r+b') as f:
 for p in wp:f.seek(p['offset']+4096);f.write(('WINDOWS_PROTECTED_'+p['name']).encode())
 f.seek(next(p['offset'] for p in wp if p['name']=='Windows C'));b=bytearray(512);b[3:11]=b'NTFS    ';b[510:]=b'\x55\xaa';f.write(b)
# Sparse ext4 can carry our regular sparse test disks without FAT's 4GiB limit.
stage=W/'files';stage.mkdir(exist_ok=True)
for name in ['source.raw','windows-original.raw']:
 dst=stage/name
 if dst.exists():dst.unlink()
 os.link(W/name,dst)
work=W/'work.ext4'
with work.open('wb') as f:f.truncate(1<<30)
run(L/'usr/sbin/mke2fs','-q','-F','-t','ext4','-b','4096','-d',stage,work)
print(W)
