#!/usr/bin/env python3
"""Local-only independent vendor experiment; original recovery/system bytes stay untouched.
Never package/distribute the generated proprietary vendor view. QEMU snapshots only.
"""
import argparse,hashlib,io,json,os,pathlib,runpy,shutil,struct,subprocess,tarfile,uuid,zlib
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--memory-image',action='store_true');p.add_argument('--output-name',default='vendor-view');p.add_argument('--native-maintenance-stubs',action='store_true');a=p.parse_args()
assert a.output_name.replace('-','').isalnum()
O=R/'build'/a.output_name;O.mkdir(exist_ok=True)
L=R/'tools/local';Q=R/'build/qemu11';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
os.environ['LD_LIBRARY_PATH']=env['LD_LIBRARY_PATH']
image_fd=None
def run(*args,**kw):return subprocess.run([str(x) for x in args],env=env,check=True,pass_fds=(() if image_fd is None else (image_fd,)),**kw)
meta=runpy.run_path(str(R/'sources/gbos-vm/image/erofs_metadata.py'))['metadata'];meta.__globals__['D']=L/'usr/bin/dump.erofs'
raw=R/'downloads/ruby-recovery.raw';lp=json.loads((R/'extracted/ruby/super.json').read_text())
vendor=next(x for x in lp['slots'][0]['partitions'] if x['name']=='vendor_a');assert len(vendor['extents'])==1
offset=vendor['extents'][0]['absolute_offset'];base=R/'extracted/ruby/vendor_a-files'
original_policy=base/'etc/selinux/precompiled_sepolicy';policy=O/'precompiled_sepolicy'
rules=['init','vendor_configs_file','file','mounton','init','system_file','file','mounton',
 'init','serial_device','chr_file','open,read,write,getattr,ioctl']
if a.native_maintenance_stubs:
 from native_vendor_in_vm import RULES
 rules=list(RULES)
with (O/'policy-changes.txt').open('wb') as f:run(R/'build/extend-vendor-policy',original_policy,policy,*rules,stdout=f)
fstab=(R/'build/compat-probe/files/fstab.android-desktop').read_text();lines=[]
for line in fstab.splitlines():
 fields=line.split()
 if fields and fields[0]=='vendor':
  if fields[2]!='erofs':continue
  fields[0]='/dev/block/by-name/GBVENDOR';fields[4]='wait,first_stage_mount';line=' '.join(fields)
 lines.append(line)
(O/'fstab.android-desktop').write_text('\n'.join(lines)+'\n')
overlays={'etc/selinux/precompiled_sepolicy':policy.read_bytes()}
if a.native_maintenance_stubs:
 for name in ['futility','crossystem','flashrom','fwtool','fwupd-binder','fwupd_blocking_update','gscutil','gscd','gsctool','vpd']:
  if (base/'bin'/name).is_file():
   overlays['bin/'+name]=b'#!/system/bin/sh\necho GBRUNCH_HARDWARE_MAINTENANCE_DISABLED >&2\nexit 1\n'
with tarfile.open(O/'overlay.tar','w',format=tarfile.PAX_FORMAT) as t:
 parents={'.'}
 for name in overlays:
  parts=pathlib.PurePosixPath(name).parts[:-1]
  for i in range(1,len(parts)+1):parents.add('/'.join(parts[:i]))
 for name in sorted(parents):
  m=meta(raw,'/' if name=='.' else '/'+name,offset)
  ti=tarfile.TarInfo(name);ti.type=tarfile.DIRTYPE;ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime']
  ti.pax_headers={} if name=='.' else {'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()};t.addfile(ti)
 for name,b in overlays.items():
  m=meta(raw,'/'+name,offset);ti=tarfile.TarInfo(name);ti.size=len(b);ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime'];ti.pax_headers={'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()};t.addfile(ti,io.BytesIO(b))
if a.memory_image:
 image_fd=os.memfd_create('gbrunch-local-vendor');image=pathlib.Path('/proc/self/fd/'+str(image_fd))
else:image=O/'vendor.erofs'
with raw.open('rb') as f:
 f.seek(offset+1024);sb=f.read(128);assert sb[:4]==bytes.fromhex('e2e1f5e0');bs=1<<sb[12]
 size=struct.unpack_from('<I',sb,36)[0]*bs;root=struct.unpack_from('<H',sb,14)[0];metadata=struct.unpack_from('<I',sb,40)[0]
 root_offset=metadata*bs+root*32;f.seek(offset+root_offset);oldroot=f.read(64)
 f.seek(offset)
 with image.open('wb') as dest:
  remaining=size
  while remaining:
   b=f.read(min(remaining,1<<20));assert b;dest.write(b);remaining-=len(b)
run(L/'usr/bin/mkfs.erofs','--incremental=data','--tar=f','-x0','-b4096','-T1230768000','-zlz4hc',image,O/'overlay.tar',stdout=subprocess.DEVNULL)
# Preserve the original root's shared-xattr reference, as gbos-vm does.
with image.open('r+b') as f:
 f.seek(root_offset);newroot=f.read(64);assert oldroot[2:4]==newroot[2:4] and not (oldroot[0]&1 or newroot[0]&1)
 f.seek(root_offset+32);f.write(oldroot[32:48]);f.seek(1024);b=bytearray(f.read(bs-1024));b[4:8]=bytes(4);crc=0xffffffff
 for value in b:
  crc^=value
  for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
 f.seek(1028);f.write(struct.pack('<I',crc))
run(L/'usr/bin/fsck.erofs',image)
actual=subprocess.check_output([str(L/'usr/bin/dump.erofs'),'--path=/etc/selinux/precompiled_sepolicy','--cat',str(image)],env=env,pass_fds=(() if image_fd is None else (image_fd,)))
assert actual==policy.read_bytes()
parent=R/'build/compat-probe/recovery-view.qcow2';info=json.loads(subprocess.check_output([str(Q/'qemu-img'),'info','--output=json',str(parent)]));prefix=O/'parent-prefix.bin'
run(Q/'qemu-img','dd','-f','qcow2','if='+str(parent),'of='+str(prefix),'bs=512','count=34',stdout=subprocess.DEVNULL)
b=prefix.read_bytes();mbr=bytearray(b[:512]);h=bytearray(b[512:1024]);tlba,count,esz=struct.unpack_from('<QII',h,72);table=bytearray(b[tlba*512:tlba*512+count*esz]);assert zlib.crc32(table)==struct.unpack_from('<I',h,88)[0]
slot=next(i for i in range(count) if not any(table[i*esz:i*esz+16]));start=(info['virtual-size']+1048575)//1048576*2048
end=start+(image.stat().st_size+511)//512-1;ts=(len(table)+511)//512;last=end+ts+1
entry=bytearray(esz);entry[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le;entry[16:32]=uuid.UUID('4ab7c002-7400-4bab-b412-43cbd52b9fb1').bytes_le
struct.pack_into('<QQQ',entry,32,start,end,0);entry[56:72]='GBVENDOR'.encode('utf-16le');table[slot*esz:(slot+1)*esz]=entry
struct.pack_into('<Q',h,32,last);struct.pack_into('<Q',h,48,end);struct.pack_into('<I',h,88,zlib.crc32(table));struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]))
bh=bytearray(h);struct.pack_into('<QQ',bh,24,last,1);struct.pack_into('<Q',bh,72,last-ts);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));struct.pack_into('<I',mbr,458,min(last,0xffffffff))
view=O/'recovery-vendor-view.qcow2'
if view.exists():raise FileExistsError('Keep previous view for review; choose a clean owned build directory')
run(Q/'qemu-img','create','-f','qcow2','-F','qcow2','-b',parent,view,(last+1)*512)
for name,position,data in [('mbr',0,mbr),('header',512,h),('table',tlba*512,table),('backup-table',(last-ts)*512,table),('backup-header',last*512,bh)]:
 p=O/(name+'.bin');p.write_bytes(data);run(Q/'qemu-io','-f','qcow2','-c',f'write -s {p} {position} {len(data)}',view,stdout=subprocess.DEVNULL)
run(Q/'qemu-io','-f','qcow2','-c',f'write -s {image} {start*512} {image.stat().st_size}',view,stdout=subprocess.DEVNULL)
(O/'manifest.json').write_text(json.dumps({'scope':'local-only QEMU vendor experiment; never redistribute proprietary vendor view','source_vendor_offset':offset,'source_vendor_bytes':size,'vendor_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'policy_sha256':hashlib.sha256(policy.read_bytes()).hexdigest(),'rules':rules,'system_partitions':'original bytes and AVB preserved','vendor':'new independent GBVENDOR, original logical vendor untouched; generated view has no Google AVB signature','view':str(view),'original_partition_records_unchanged':True},indent=2)+'\n')
print(view)
