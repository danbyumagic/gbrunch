#!/usr/bin/env python3
"""Disposable Work-only runtime view; proprietary vendor stays local, never publish."""
import argparse,pathlib,subprocess,os,json,hashlib
p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=pathlib.Path);p.add_argument('--compat',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
r=pathlib.Path(__file__).resolve().parents[1];w=a.work.resolve();child=a.output.resolve();compat=a.compat.resolve()
assert child.is_relative_to(r/'build') and not child.exists();assert w.is_relative_to(r/'build') and compat.is_relative_to(r/'build')
res=json.loads((w/'update-result.json').read_text());target=next(p for p in res['partitions'] if p['name']=='GBVENDOR');assert res['vendor_bytes']<=target['bytes'];q=r/'build/qemu11'
subprocess.run([str(q/'qemu-img'),'create','-f','qcow2','-F','qcow2','-b',str(r/'build/native-android-gpu/uefi-usb-view.qcow2'),str(child)],check=True,stdout=subprocess.DEVNULL)
f=os.memfd_create('local-native-vendor');env=os.environ.copy();env['LD_LIBRARY_PATH']=str(r/'tools/local/usr/lib/x86_64-linux-gnu')
with os.fdopen(os.dup(f),'wb') as output:subprocess.run([str(r/'tools/local/usr/bin/mcopy'),'-i',str(w/'work.fat'),'::/vendor.erofs','-'],env=env,stdout=output,check=True)
with os.fdopen(os.dup(f),'rb') as inp:
 inp.seek(0);assert hashlib.file_digest(inp,'sha256').hexdigest()==res['vendor_sha256']
assert os.fstat(f).st_size==res['vendor_bytes']
def delta_write(new_fd,offset,size):
 old=os.memfd_create('old-parent-range')
 opts=f'driver=raw,offset={offset},size={size},file.driver=qcow2,file.file.driver=file,file.file.filename={r}/build/native-android-gpu/uefi-usb-view.qcow2'
 subprocess.run([str(q/'qemu-img'),'convert','--image-opts',opts,'-O','raw','-S','64k','/proc/self/fd/'+str(old)],pass_fds=(old,),check=True,stdout=subprocess.DEVNULL)
 assert os.fstat(old).st_size==size
 for start in range(0,size,1<<20):
  data=os.pread(new_fd,min(1<<20,size-start),start)
  if data==os.pread(old,len(data),start):continue
  chunk=os.memfd_create('delta-block');os.write(chunk,data)
  subprocess.run([str(q/'qemu-io'),'-f','qcow2','-c',f'write -s /proc/self/fd/{chunk} {offset+start} {len(data)}',str(child)],pass_fds=(chunk,),check=True,stdout=subprocess.DEVNULL);os.close(chunk)
 os.close(old)
delta_write(f,target['offset'],res['vendor_bytes'])
assert compat.stat().st_size==67108864
with compat.open('rb') as c:delta_write(c.fileno(),19070451712,67108864)
print(child)
