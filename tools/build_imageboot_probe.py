#!/usr/bin/env python3
"""Local file-only NTFS/nested-GPT probe using the unchanged Google kernel.
Never accepts devices, never rewrites Google images, never publishes a ramdisk.
"""
import pathlib,gzip,stat,subprocess,os,re,json,hashlib,struct,zlib,uuid
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/imageboot-probe';B.mkdir(exist_ok=True)
L=R/'tools/local';N=R/'tools/imageboot';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(N/'usr/lib/x86_64-linux-gnu')+':'+str(L/'usr/lib/x86_64-linux-gnu')
def run(*a,**kw):return subprocess.run([str(x) for x in a],env=env,check=True,**kw)
def entry(name,b,mode,i):
 n=name.encode()+b'\0';v=[i,mode,0,0,1,0,len(b),0,0,0,0,len(n),0];h=b'070701'+b''.join(f'{x:08x}'.encode() for x in v)+n;return h+bytes(-len(h)%4)+b+bytes(-len(b)%4)
files={}
def add(path,name,mode=stat.S_IFREG|0o755):files[name]=(mode,pathlib.Path(path).read_bytes())
add(L/'usr/bin/busybox','imageboot/busybox');add(N/'usr/bin/ntfs-3g','imageboot/ntfs-3g');add('/usr/sbin/blkid','imageboot/blkid')
s=subprocess.check_output(['ldd',str(N/'usr/bin/ntfs-3g')],env=env,text=True)+subprocess.check_output(['ldd','/usr/sbin/blkid'],text=True)
for line in s.splitlines():
 m=re.search(r'=>\s+(/\S+)\s+\(',line) or re.search(r'^\s*(/\S+)\s+\(',line)
 if m:
  p=pathlib.Path(m[1]);name=('lib64/'+p.name if p.name.startswith('ld-linux') else 'lib/x86_64-linux-gnu/'+p.name);add(p,name)
init=(R/'tools/imageboot_probe_init.sh').read_bytes();files['imageboot/init']=(stat.S_IFREG|0o755,init)
for n in ['imageboot','lib','lib64','lib/x86_64-linux-gnu']:files[n]=(stat.S_IFDIR|0o755,b'')
overlay=b''.join(entry(n,b,m,980000+i) for i,(n,(m,b)) in enumerate(sorted(files.items())))+entry('TRAILER!!!',b'',0,989999)
original=gzip.decompress((R/'build/native-android-gpu/initrd.gz').read_bytes());(B/'initrd.gz').write_bytes(gzip.compress(original+overlay,mtime=0))
# Nested 8MiB GPT disk with a 4MiB ext4 partition, stored as a regular NTFS file.
inner=B/'gbrunch.img';fs=B/'inner.ext4';stage=B/'marker';stage.mkdir(exist_ok=True);(stage/'marker.txt').write_text('GBRUNCH_NESTED_IMAGE_OK\n')
with fs.open('wb') as f:f.truncate(4<<20)
run(L/'usr/sbin/mke2fs','-q','-F','-t','ext4','-b','4096','-d',stage,fs)
size=8<<20;sectors=size//512;es=bytearray(128*128);e=bytearray(128);e[:16]=uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le;e[16:32]=uuid.UUID('91372943-cd97-40af-9d7f-bf4cfe95ca60').bytes_le;struct.pack_into('<QQQ',e,32,2048,10239,0);e[56:70]='GBPROBE'.encode('utf-16le');es[:128]=e
h=bytearray(512);h[:8]=b'EFI PART';struct.pack_into('<IIII',h,8,0x10000,92,0,0);struct.pack_into('<QQQQ',h,24,1,sectors-1,34,sectors-34);h[56:72]=uuid.UUID('e3c1a1a5-b69f-41c4-a93d-7aa46e9a474b').bytes_le;struct.pack_into('<QIII',h,72,2,128,128,zlib.crc32(es));struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,sectors-1,1);struct.pack_into('<Q',bh,72,sectors-33);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(512);mbr[450]=0xee;struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
with inner.open('wb') as f:
 f.truncate(size)
 for off,data in [(0,mbr),(512,h),(1024,es),(1<<20,fs.read_bytes()),((sectors-33)*512,es),((sectors-1)*512,bh)]:f.seek(off);f.write(data)
outer=B/'windows-test.ntfs'
with outer.open('wb') as f:f.truncate(96<<20)
run(N/'usr/sbin/mkntfs','-F','-Q','-L','GBRUNCH_TEST_HOST',outer,stdout=subprocess.DEVNULL)
run(N/'usr/sbin/ntfscp',outer,inner,'/gbrunch.img')
(B/'build.json').write_text(json.dumps(dict(scope='local diagnostic fixture, not full Android boot',kernel_sha256=hashlib.sha256((R/'extracted/ruby/boot_a/kernel').read_bytes()).hexdigest(),original_kernel_unchanged=True,google_system_images_changed=False,ntfs_fixture_bytes=outer.stat().st_size,nested_image_bytes=size,devices_accessed=False),indent=2)+'\n')
print(B)
