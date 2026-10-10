#!/usr/bin/env python3
"""Only runs in a preparation VM: erase selected USB and store local recovery view."""
import pathlib,subprocess,hashlib,json,struct,fcntl,os,uuid,zlib,traceback
from dualboot_installer import capacity,require,read_layout,COMPAT_HASH,SOURCE_GUIDS
M=1<<20;G=1<<30;USB=pathlib.Path('/dev/vda');SRC=pathlib.Path('/dev/vdc');W=pathlib.Path('/work')
def run(*args):return subprocess.run([str(a) for a in args],check=True)
def main():
 require('gbrunch.prepare_usb=1' in pathlib.Path('/proc/cmdline').read_text(),'Not preparation mode')
 require(pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip()=='QEMU','Must be QEMU preparation VM')
 require(pathlib.Path('/sys/class/block/vda/serial').read_text().strip()=='GBRUNCH_PREP_USB','Wrong target serial')
 req=json.loads((W/'prepare-request.json').read_text());size=capacity(USB)
 require(size==req['usb_bytes'] and 28*G<=size<=40*G,'USB capacity mismatch')
 with SRC.open('rb') as f:require(struct.unpack('I',fcntl.ioctl(f.fileno(),0x125e,bytes(4)))[0]==1,'Source must be read-only')
 source_bytes=capacity(SRC);require(source_bytes==req['source_bytes'],'Source size changed')
 layout=read_layout(SRC);by={p['name']:p for p in layout['parts']}
 require(all(by.get(n,{}).get('guid')==g for n,g in SOURCE_GUIDS.items()),'Wrong source GPT')
 # Target GPT has fixed installer extents and one payload filesystem. Backup is
 # always at actual physical capacity, even on different marketed 32 GB drives.
 specs=[('GBINSTALL_E',1*M,128*M,'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'),('GBINSTALL',129*M,128*M,'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'),('GBPAYLOAD',257*M,26*G,'0fc63daf-8483-4772-8e79-3d69d8477de4')]
 sectors=size//512;table=bytearray(16384)
 for i,(name,off,length,typ) in enumerate(specs):
  ent=bytearray(128);ent[:16]=uuid.UUID(typ).bytes_le;ent[16:32]=uuid.uuid4().bytes_le;struct.pack_into('<QQQ',ent,32,off//512,(off+length)//512-1,0);n=name.encode('utf-16le');ent[56:56+len(n)]=n;table[i*128:(i+1)*128]=ent
 h=bytearray(512);h[:8]=b'EFI PART';struct.pack_into('<IIII',h,8,0x10000,92,0,0);struct.pack_into('<QQQQ',h,24,1,sectors-1,34,sectors-34);h[56:72]=uuid.uuid4().bytes_le;struct.pack_into('<QIII',h,72,2,128,128,zlib.crc32(table));struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,sectors-1,1);struct.pack_into('<Q',bh,72,sectors-33);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(512);mbr[450]=0xee;struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
 with USB.open('r+b',buffering=0) as out:
  fcntl.flock(out,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for off,b in [(0,mbr),(512,h),(1024,table),((sectors-33)*512,table),((sectors-1)*512,bh)]:out.seek(off);out.write(b)
  with (W/'installer.img').open('rb') as f:
   for _,off,length,_ in specs[:2]:
    f.seek(off);out.seek(off)
    for pos in range(0,length,4*M):out.write(f.read(min(4*M,length-pos)))
  os.fsync(out.fileno());fcntl.ioctl(out.fileno(),0x125f)
 run('mdev','-s');payload='/dev/vda3'
 run('mke2fs','-F','-t','ext4','-m','0','-i','1048576','-L','GBPAYLOAD','-O','^metadata_csum_seed,^orphan_file',payload)
 pathlib.Path('/payload').mkdir(exist_ok=True);run('mount','-t','ext4',payload,'/payload')
 h=hashlib.sha256();done=0
 with SRC.open('rb',buffering=0) as f,open('/payload/source.raw','xb',buffering=0) as out:
  while done<source_bytes:
   b=f.read(min(4*M,source_bytes-done));require(bool(b),'Source short read');h.update(b)
   if b.strip(b'\0'):out.write(b)
   else:out.seek(len(b),1)
   done+=len(b)
   if done%(1<<30)<4*M:print('Copying payload %.1f / %.1f GB'%(done/1e9,source_bytes/1e9),flush=True)
  out.truncate(source_bytes);os.fsync(out.fileno())
 md=dict(format='GBRUNCH standalone source v1',source_bytes=source_bytes,source_sha256=h.hexdigest(),compat_sha256=COMPAT_HASH,official_recovery=req['official_recovery'],assembly_manifest=req['assembly_manifest'])
 pathlib.Path('/payload/SOURCE-MANIFEST.json').write_text(json.dumps(md,indent=2)+'\n');os.sync();run('umount','/payload');run('e2fsck','-f','-n',payload)
 run('mount','-t','ext4','-o','ro,noload',payload,'/payload');verify=hashlib.sha256()
 with open('/payload/source.raw','rb') as f:
  for b in iter(lambda:f.read(4*M),b''):verify.update(b)
 require(verify.hexdigest()==h.hexdigest(),'USB payload readback mismatch');run('umount','/payload')
 require(len(read_layout(USB)['parts'])==3,'USB GPT readback failed')
 (W/'prepare-result.json').write_text(json.dumps(dict(passed=True,usb_bytes=size,payload=md,readback_sha256=verify.hexdigest(),payload_fsck_passed=True),indent=2)+'\n');print('STANDALONE_USB_PREP_PASS',flush=True)
if __name__=='__main__':
 try:main();(W/'status.txt').write_text('0\n')
 except Exception:
  traceback.print_exc();(W/'status.txt').write_text('1\n')
