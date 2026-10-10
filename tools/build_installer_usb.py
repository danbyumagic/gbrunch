#!/usr/bin/env python3
"""Redistributable Linux installer USB; no Google recovery/vendor/kernel bytes."""
import pathlib,subprocess,os,gzip,lzma,json,stat,re,hashlib,struct,uuid,zlib,shutil
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];B=pathlib.Path(os.environ.get('GBRUNCH_INSTALLER_BUILD',str(R/'build/dualboot-installer')));B.mkdir(exist_ok=True);L=R/'tools/local';deps=R/'tools/installer-deps';e=os.environ.copy();e['LD_LIBRARY_PATH']=str(deps/'usr/lib/x86_64-linux-gnu')+':'+str(L/'usr/lib/x86_64-linux-gnu')
def run(*a,**kw):return subprocess.run([str(x) for x in a],env=e,check=True,**kw)
# Own GRUB bootstrap finds only the new internal ESP label, never the Windows ESP.
redirect=B/'internal-redirect.cfg';redirect.write_text('insmod part_gpt\ninsmod fat\nsearch --no-floppy --label --set=root GBRUNCH_INT\nconfigfile /EFI/GBRUNCH/grub.cfg\n')
run(L/'usr/bin/grub-mkstandalone','-O','x86_64-efi','-d',L/'usr/lib/grub/x86_64-efi','--fonts=','--locales=','-o',B/'internal-BOOTX64.EFI',f'boot/grub/grub.cfg={redirect}')
files={};origins={}
def add(name,b,mode=stat.S_IFREG|0o644,source='owned source'):
 files[name]=(mode,b);origins[name]=dict(source=str(source),sha256=hashlib.sha256(b).hexdigest())
def copy(path,name,executable=False):
 p=pathlib.Path(path);add(name,p.read_bytes(),stat.S_IFREG|(0o755 if executable else 0o644),p)
def executable(path,name):
 copy(path,name,True)
 for line in subprocess.check_output(['ldd',str(path)],env=e,text=True,stderr=subprocess.DEVNULL).splitlines():
  m=re.search(r'=>\s+(/\S+)\s+\(',line) or re.search(r'^\s*(/\S+)\s+\(',line)
  if m:
   p=pathlib.Path(m[1]);dest=('lib64/'+p.name if p.name.startswith('ld-linux') else 'lib/x86_64-linux-gnu/'+p.name);copy(p,dest,True)
for name in ['mcopy','mdir','mformat','mlabel']:executable(L/'usr/bin'/name,'bin/'+name)
executable(L/'usr/sbin/fsck.fat','bin/fsck.fat');executable('/usr/sbin/blkid','bin/blkid');executable('/usr/sbin/losetup','bin/losetup');executable(deps/'usr/bin/efibootmgr','bin/efibootmgr')
# glibc codepage converters are required by mtools for FAT names.
for p in pathlib.Path('/usr/lib/x86_64-linux-gnu/gconv').rglob('*'):
 if p.is_file():copy(p,'usr/lib/x86_64-linux-gnu/gconv/'+str(p.relative_to('/usr/lib/x86_64-linux-gnu/gconv')))
for name in ['dualboot_installer.py','inspect_recovery.py','installer_console.py','test_installer_guest.py','test_installed_layout.py','standalone_bootstrap.py','prepare_standalone_guest.py']:copy(R/'tools'/name,'installer/'+name)
copy(B/'internal-BOOTX64.EFI','installer/internal-BOOTX64.EFI')
# Matching Debian module closure for physical NVMe/USB, keyboard, EFI variables,
# and ext4 work/test files. No network or GPU acceleration is needed by installer.
version=next((R/'tools/hp-kernel/usr/lib/modules').iterdir()).name;root=R/'tools/hp-kernel/usr/lib/modules'/version
index={p.name.removesuffix('.ko.xz').replace('-','_'):p for p in root.rglob('*.ko.xz')};order=[];chosen=set()
def info(b):
 shoff=struct.unpack_from('<Q',b,40)[0];size,count,si=struct.unpack_from('<HHH',b,58);ss=[struct.unpack_from('<IIQQQQIIQQ',b,shoff+i*size) for i in range(count)];st=ss[si];names=b[st[4]:st[4]+st[5]]
 for s in ss:
  if names[s[0]:names.find(b'\0',s[0])]==b'.modinfo':return [x.decode() for x in b[s[4]:s[4]+s[5]].split(b'\0') if x]
 return []
def select(n):
 n=n.replace('-','_')
 if n in chosen or n not in index:return
 chosen.add(n);p=index[n];b=lzma.decompress(p.read_bytes());rows=info(b)
 for d in next((x[8:] for x in rows if x.startswith('depends=')),'').split(','):
  if d:select(d)
 copy_name=p.name.removesuffix('.xz');add('installer-modules/'+copy_name,b,source=p);order.append(copy_name)
for n in ['nvme','vmd','xhci_pci','usb_storage','uas','sd_mod','vfat','nls_cp437','nls_ascii','nls_utf8','usbhid','hid_generic','evdev','efivarfs','crc32c_generic','crc32c_intel','ext4','virtio_pci','virtio_blk','simpledrm','efifb','fbcon']:select(n)
add('etc/installer-module-order',('\n'.join(order)+'\n').encode())
for n in ['installer','installer-modules','logs','work']:add(n,b'',stat.S_IFDIR|0o755)
copy(R/'tools/installer_init.sh','init',True)
for name in list(files):
 for parent in pathlib.PurePosixPath(name).parents:
  if str(parent)!='.' and str(parent) not in files:add(str(parent),b'',stat.S_IFDIR|0o755)
extra=b''.join(entry(n,b,m,1100000+i) for i,(n,(m,b)) in enumerate(sorted(files.items())))+entry('TRAILER!!!',b'',0,1199999)
base=gzip.decompress((R/'build/userdata-maintenance/initrd.gz').read_bytes());(B/'initrd.gz').write_bytes(gzip.compress(base+extra,compresslevel=6,mtime=0))
if not (B/'linux-kernel').exists():shutil.copyfile(R/'tools/hp-kernel/boot'/('vmlinuz-'+version),B/'linux-kernel')
(B/'runtime-manifest.json').write_text(json.dumps(dict(scope='Linux installer only; no Google OS bytes',kernel_sha256=hashlib.sha256((B/'linux-kernel').read_bytes()).hexdigest(),initrd_sha256=hashlib.sha256((B/'initrd.gz').read_bytes()).hexdigest(),files=origins,modules=order),indent=2)+'\n')
# Produce a small GPT USB disk: 128MiB EFI + 128MiB installer log volume.
def gpt_image(path,parts,size):
 sectors=size//512;table=bytearray(16384)
 for i,p in enumerate(parts):
  ent=bytearray(128);ent[:16]=uuid.UUID(p['type']).bytes_le;ent[16:32]=uuid.UUID(p['guid']).bytes_le;struct.pack_into('<QQQ',ent,32,p['offset']//512,(p['offset']+p['bytes'])//512-1,0);n=p['name'].encode('utf-16le');ent[56:56+len(n)]=n;table[i*128:(i+1)*128]=ent
 h=bytearray(512);h[:8]=b'EFI PART';struct.pack_into('<IIII',h,8,0x10000,92,0,0);struct.pack_into('<QQQQ',h,24,1,sectors-1,34,sectors-34);h[56:72]=uuid.UUID('11a27468-79ab-48ec-acda-2ed304f964b5').bytes_le;struct.pack_into('<QIII',h,72,2,128,128,zlib.crc32(table));struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,sectors-1,1);struct.pack_into('<Q',bh,72,sectors-33);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(512);mbr[450]=0xee;struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
 with path.open('wb') as f:
  f.truncate(size)
  for off,data in [(0,mbr),(512,h),(1024,table),((sectors-33)*512,table),((sectors-1)*512,bh)]:f.seek(off);f.write(data)
  for p in parts:
   with pathlib.Path(p['file']).open('rb') as src:
    for pos in range(0,p['bytes'],1<<20):
     b=src.read(min(1<<20,p['bytes']-pos))
     if b.strip(b'\0'):f.seek(p['offset']+pos);f.write(b)
# Own installer bootloader searches its unique installer EFI label.
red=B/'usb-redirect.cfg';red.write_text('insmod part_gpt\ninsmod fat\nsearch --no-floppy --label --set=root GBINSTALL_E\nconfigfile /EFI/GBRUNCH/grub.cfg\n')
run(L/'usr/bin/grub-mkstandalone','-O','x86_64-efi','-d',L/'usr/lib/grub/x86_64-efi','--fonts=','--locales=','-o',B/'BOOTX64.EFI',f'boot/grub/grub.cfg={red}')
cfg=B/'grub.cfg';cfg.write_text("set timeout=5\nset default=0\nmenuentry 'GBRUNCH installer: inspect disks first' {\n linux /EFI/GBRUNCH/linux-kernel rdinit=/init console=tty0 console=ttyS0,115200 loglevel=4 gbrunch.installer=1\n initrd /EFI/GBRUNCH/initrd.gz\n}\nmenuentry 'UEFI firmware settings' { fwsetup }\n")
for n,label in [('efi.fat','GBINSTALL_E'),('logs.fat','GBINSTALL')]:
 f=B/n
 with f.open('wb') as out:out.truncate(128<<20)
 run(L/'usr/bin/mformat','-i',f,'-F','-v',label,'::')
run(L/'usr/bin/mmd','-i',B/'efi.fat','::/EFI','::/EFI/BOOT','::/EFI/GBRUNCH')
for f,n in [(B/'BOOTX64.EFI','BOOT/BOOTX64.EFI'),(B/'linux-kernel','GBRUNCH/linux-kernel'),(B/'initrd.gz','GBRUNCH/initrd.gz'),(cfg,'GBRUNCH/grub.cfg')]:run(L/'usr/bin/mcopy','-i',B/'efi.fat',f,'::/EFI/'+n)
marker=B/'GBRUNCH-INSTALLER.txt';marker.write_text('GBRUNCH Linux dualboot installer v1\n');run(L/'usr/bin/mcopy','-i',B/'logs.fat',marker,'::/')
parts=[dict(name='GBINSTALL_E',guid='4fe080cf-cb3e-4bd2-96f8-944140950d72',type='c12a7328-f81f-11d2-ba4b-00a0c93ec93b',offset=1<<20,bytes=128<<20,file=str(B/'efi.fat')),dict(name='GBINSTALL',guid='3718f757-a9fb-4556-a10d-a7907eafda47',type='ebd0a0a2-b9e5-4433-87c0-68b6b72699c7',offset=129<<20,bytes=128<<20,file=str(B/'logs.fat'))]
image=B/'gbrunch-installer-v1.img';gpt_image(image,parts,260<<20)
(B/'usb-manifest.json').write_text(json.dumps(dict(parts=parts,bytes=image.stat().st_size,sha256=hashlib.sha256(image.read_bytes()).hexdigest(),google_images_included=False),indent=2)+'\n');print(B)
