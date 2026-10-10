#!/usr/bin/env python3
"""Build an owned EFI diagnostic disk file; never opens host block devices."""
import gzip,hashlib,json,lzma,os,pathlib,struct,subprocess,uuid,zlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'build/hp-diagnostics';OUT.mkdir(parents=True,exist_ok=True)
LOCAL=ROOT/'tools/local'; env=os.environ.copy()
env['LD_LIBRARY_PATH']=str(LOCAL/'usr/lib/x86_64-linux-gnu')
env['PATH']=str(LOCAL/'usr/bin')+':'+str(LOCAL/'usr/sbin')+':'+env['PATH']
def run(*a):subprocess.run([str(x) for x in a],env=env,check=True)
for name in ['esp.fat','gbrunch-hp-diagnostics.img','BOOTX64.EFI']:
 p=OUT/name;assert not p.is_symlink() and (not p.exists() or p.is_file())
run('gcc','-O2','-static','-Wall','-Wextra','-o',OUT/'hp-media-id',ROOT/'tools/hp_media_id.c')
for exe,source,flags in [('hp-input-probe','hp_input_probe.c',[]),('hp-camera-probe','hp_camera_probe.c',[]),('hp-suspend-test','hp_suspend_test.c',[]),('hp-cpu-gfni','test_gfni.c',[]),('hp-cpu-vnni','test_vnni.c',['-DEMULATED_AVX'])]:
 run('gcc','-O2','-static',*flags,'-o',OUT/exe,ROOT/'tools'/source)
run('gcc','-O2','-static','-D__user=','-I',ROOT/'tools/hp-uapi','-o',OUT/'hp-device-probe',ROOT/'tools/hp_device_probe.c')
run('gcc','-O2','-static','-Wall','-Wextra','-D__user=','-I',ROOT/'tools/hp-uapi','-o',OUT/'hp-xe-graphics',ROOT/'tools/hp_xe_graphics.c')
busy=(LOCAL/'usr/bin/busybox').read_bytes()
apps=subprocess.check_output([str(LOCAL/'usr/bin/busybox'),'--list'],text=True).splitlines()
version=next((ROOT/'tools/hp-kernel/usr/lib/modules').iterdir()).name
kernel_dir=ROOT/'tools/hp-kernel/usr/lib/modules'/version
# Small, matching Debian module closure; no network/audio/GPU/firmware-update modules.
index={p.name.removesuffix('.xz').removesuffix('.ko').replace('-','_'):p for p in kernel_dir.rglob('*.ko.xz')}
def modinfo(b):
 shoff=struct.unpack_from('<Q',b,40)[0];size,count,si=struct.unpack_from('<HHH',b,58)
 ss=[struct.unpack_from('<IIQQQQIIQQ',b,shoff+i*size) for i in range(count)]
 st=ss[si];names=b[st[4]:st[4]+st[5]]
 for s in ss:
  name=names[s[0]:names.find(b'\0',s[0])]
  if name==b'.modinfo':return [x.decode() for x in b[s[4]:s[4]+s[5]].split(b'\0') if x]
 return []
selected={};order=[]
def select(name):
 name=name.replace('-','_')
 if name in selected or name not in index:return
 b=lzma.decompress(index[name].read_bytes());info=modinfo(b)
 selected[name]=(index[name].name.removesuffix('.xz'),b,info)
 deps=next((x[8:] for x in info if x.startswith('depends=')),'').split(',')
 for dep in deps:
  if dep:select(dep)
 order.append(name)
for name in ['nvme','xhci_pci','ehci_pci','uhci_hcd','usb_storage','uas','sd_mod','vfat','nls_cp437','nls_ascii','nls_utf8','evdev','pinctrl_meteorlake','idma64','usbhid','hid_generic','hid_multitouch','i2c_hid_acpi','intel_lpss_pci','intel_lpss_acpi','i2c_designware_platform','i2c_designware_pci','virtio_pci','virtio_blk']:
 select(name)
core_order=list(order)
extra_names=['iwlwifi','iwlmvm','btusb','btintel','uvcvideo','intel_ish_ipc','intel_ishtp_hid','hid_sensor_hub','hid_sensor_accel_3d','hid_sensor_gyro_3d','hid_sensor_incl_3d','hid_sensor_rotation','hp_wmi','intel_vbtn','wmi_bmof','thunderbolt','snd_soc_hdac_hda','snd_soc_hda_codec','snd_sof_pci_intel_mtl','snd_soc_skl_hda_dsp','snd_soc_sof_sdw','snd_hda_scodec_cs35l41_i2c','snd_hda_scodec_cs35l41_spi','snd_hda_codec_realtek','snd_hda_codec_hdmi','snd_hda_intel','mei_me','mei_pxp','mei_hdcp','mei_gsc_proxy','i915']
for name in extra_names:select(name)
extra_order=[n for n in order if n not in core_order]
# Persist selected metadata for reproducible matching-module checks.
(OUT/'linux-modules.json').write_text(json.dumps([{'name':n,'file':selected[n][0],'sha256':hashlib.sha256(selected[n][1]).hexdigest(),'modinfo':selected[n][2]} for n in order],indent=2)+'\n')
def make_initrd(mode):
 entries=[]
 def add(name,modebits,data=b''):
  n=name.encode()+b'\0';f=[len(entries)+1,modebits,0,0,1,0,len(data),0,0,0,0,len(n),0]
  x=b'070701'+b''.join(f'{v:08x}'.encode() for v in f)+n;x+=bytes(-len(x)%4);x+=data;x+=bytes(-len(data)%4);entries.append(x)
 for d in ['bin','dev','etc','proc','sys','run','tmp','modules','usr','usr/share','lib','lib64','lib/x86_64-linux-gnu','lib/modules','lib/modules/'+version]:add(d,0o040755)
 add('bin/busybox',0o100755,busy)
 for app in apps:
  if app!='busybox':add('bin/'+app,0o120777,b'busybox')
 add('bin/hp-media-id',0o100755,(OUT/'hp-media-id').read_bytes())
 add('etc/gbrunch-mode',0o100644,(mode+'\n').encode())
 add('init',0o100755,(ROOT/'tools/hp_probe_init.sh').read_bytes())
 if mode=='linux':
  add('etc/module-load-order',0o100644,('\n'.join(selected[n][0] for n in core_order)+'\n').encode())
  add('etc/extra-module-load-order',0o100644,('\n'.join(selected[n][0] for n in extra_order)+'\n').encode())
  add('etc/google-cmdline',0o100644,b'rdinit=/init loglevel=8 ignore_loglevel printk.time=1 printk.devkmsg=on log_buf_len=8M initcall_debug panic=0 console=ttyS0,115200 earlycon=uart8250,io,0x3f8,115200 8250.nr_uarts=4 gbrunch.batch=1\n')
  for exe in ['hp-input-probe','hp-camera-probe','hp-device-probe','hp-suspend-test','hp-cpu-gfni','hp-cpu-vnni']:add('bin/'+exe,0o100755,(OUT/exe).read_bytes())
  add('etc/hp-batch-packages.json',0o100644,(ROOT/'evidence/hp-batch-packages.json').read_bytes())
  batch=ROOT/'tools/hp-batch'
  for source,dest in [('usr/sbin/kexec','bin/kexec'),('usr/sbin/iw','bin/iw'),('usr/bin/aplay','bin/aplay'),('usr/bin/speaker-test','bin/speaker-test')]:add(dest,0o100755,(batch/source).read_bytes())
  libs=batch/'usr/lib/x86_64-linux-gnu'
  for p in sorted(libs.glob('*.so*')):
   if p.is_file():add('lib/x86_64-linux-gnu/'+p.name,0o100755,p.read_bytes())
  add('lib64/ld-linux-x86-64.so.2',0o100755,(libs/'ld-linux-x86-64.so.2').read_bytes())
  def tree(folder,dest):
   add(dest,0o040755)
   for p in sorted(folder.rglob('*')):
    rel=dest+'/'+str(p.relative_to(folder))
    if p.is_symlink():add(rel,0o120777,os.readlink(p).encode())
    elif p.is_dir():add(rel,0o040755)
    elif p.is_file():add(rel,0o100644,p.read_bytes())
  tree(batch/'usr/lib/firmware','lib/firmware')
  tree(batch/'usr/share/alsa','usr/share/alsa')
  tree(batch/'usr/share/doc','usr/share/doc')
  if (batch/'usr/share/sounds/alsa').exists():tree(batch/'usr/share/sounds/alsa','usr/share/sounds/alsa')
  add('etc/asound.conf',0o100644,b'</usr/share/alsa/alsa.conf>\n')
  add('bin/hp-batch-tests',0o100755,(ROOT/'tools/hp_batch_tests.sh').read_bytes())
  dep=[];aliases=[]
  for name in order:
   filename,b,info=selected[name];add('lib/modules/'+version+'/'+filename,0o100644,b)
   deps=next((x[8:] for x in info if x.startswith('depends=')),'').split(',')
   dep.append(filename+': '+ ' '.join(selected[d.replace('-','_')][0] for d in deps if d.replace('-','_') in selected))
   aliases += ['alias '+x[6:]+' '+name for x in info if x.startswith('alias=')]
  add('lib/modules/'+version+'/modules.dep',0o100644,('\n'.join(dep)+'\n').encode())
  add('lib/modules/'+version+'/modules.alias',0o100644,('\n'.join(aliases)+'\n').encode())
  add('lib/modules/'+version+'/modules.builtin',0o100644,(kernel_dir/'modules.builtin').read_bytes())
 else:
  xe=ROOT/'build/xe-probe'
  assert (xe/'manifest.json').exists(), 'Run prepare_original_xe.py first'
  for d in ['xe','lib/firmware','lib/firmware/i915']:add(d,0o040755)
  for f in sorted((xe/'modules').iterdir()):add('xe/'+f.name,0o100644,f.read_bytes())
  for f in sorted((xe/'firmware/i915').iterdir()):add('lib/firmware/i915/'+f.name,0o100644,f.read_bytes())
  add('bin/hp-xe-graphics',0o100755,(OUT/'hp-xe-graphics').read_bytes())
  add('etc/xe-load-order',0o100644,(xe/'module-load-order').read_bytes())
  add('etc/xe-manifest.json',0o100644,(xe/'manifest.json').read_bytes())
  for name in ['virtio_pci_modern_dev','virtio_pci_legacy_dev','virtio_pci','virtio_blk']:
   add('modules/'+name+'.ko',0o100644,(ROOT/'extracted/ruby/system_dlkm_a-files/lib/modules'/f'{name}.ko').read_bytes())
 add('TRAILER!!!',0)
 path=OUT/(mode+'-initrd.gz');path.write_bytes(gzip.compress(b''.join(entries),compresslevel=6,mtime=0));return path
linux_initrd=make_initrd('linux');google_initrd=make_initrd('google')
linux_kernel=ROOT/'tools/hp-kernel/boot'/('vmlinuz-'+version)
google_kernel=ROOT/'extracted/ruby/boot_a/kernel'
verbose='rdinit=/init loglevel=8 ignore_loglevel printk.time=1 printk.devkmsg=on log_buf_len=8M initcall_debug panic=0'
linux_cmd=verbose+' console=ttyS0,115200 console=tty0 nomodeset'
google_cmd=verbose+' console=ttyS0,115200 earlycon=uart8250,io,0x3f8,115200 8250.nr_uarts=4'
cfg='''serial --unit=0 --speed=115200
terminal_output console serial
terminal_input console serial
set timeout=12
set default=4
set pager=1
menuentry "1. Full HP test batch, then Google kernel (recommended)" {
 linux /EFI/GBRUNCH/linux-kernel '''+linux_cmd.replace(' nomodeset','')+''' gbrunch.batch=1
 initrd /EFI/GBRUNCH/linux-initrd.gz
}
menuentry "2. Original Google kernel + Intel Xe - logs, then powers off" {
 echo "The Google kernel has no graphical text console. The screen may stop updating."
 echo "Wait up to 90 seconds, then read GBRUNCH-LOGS on this USB drive from macOS."
 sleep 5
 linux /EFI/GBRUNCH/google-kernel '''+google_cmd+'''
 initrd /EFI/GBRUNCH/google-initrd.gz
}
menuentry "3. Firmware setup" {
 fwsetup
}
menuentry "4. Linux automatic test (powers off)" {
 linux /EFI/GBRUNCH/linux-kernel '''+linux_cmd+''' gbrunch.autopoweroff=1
 initrd /EFI/GBRUNCH/linux-initrd.gz
}
menuentry "5. FINAL Xe render + color bars test (default, powers off)" {
 linux /EFI/GBRUNCH/google-kernel '''+google_cmd+''' gbrunch.autopoweroff=1 gbrunch.graphics=1
 initrd /EFI/GBRUNCH/google-initrd.gz
}
menuentry "6. Basic inventory only - fallback console, no extra drivers" {
 linux /EFI/GBRUNCH/linux-kernel '''+linux_cmd+'''
 initrd /EFI/GBRUNCH/linux-initrd.gz
}
'''
(OUT/'grub.cfg').write_text(cfg)
(OUT/'redirect.cfg').write_text('insmod part_gpt\ninsmod fat\nsearch --no-floppy --fs-uuid --set=root 4742-4832\nconfigfile /EFI/GBRUNCH/grub.cfg\n')
run(LOCAL/'usr/bin/grub-mkstandalone','-O','x86_64-efi','-d',LOCAL/'usr/lib/grub/x86_64-efi','--fonts=','--locales=','-o',OUT/'BOOTX64.EFI',f'boot/grub/grub.cfg={OUT}/redirect.cfg')
esp=OUT/'esp.fat'
with esp.open('wb') as f:f.truncate(256*1024*1024)
run(LOCAL/'usr/sbin/mkfs.fat','-F','32','-i','47424832','-n','GBRUNCH_HP',esp)
run(LOCAL/'usr/bin/mmd','-i',esp,'::/EFI','::/EFI/BOOT','::/EFI/GBRUNCH','::/GBRUNCH-LOGS')
files={OUT/'BOOTX64.EFI':'/EFI/BOOT/BOOTX64.EFI',OUT/'grub.cfg':'/EFI/GBRUNCH/grub.cfg',linux_kernel:'/EFI/GBRUNCH/linux-kernel',google_kernel:'/EFI/GBRUNCH/google-kernel',linux_initrd:'/EFI/GBRUNCH/linux-initrd.gz',google_initrd:'/EFI/GBRUNCH/google-initrd.gz'}
marker=OUT/'GBRUNCH-MEDIA.TXT';marker.write_text('GBRUNCH-HP-DIAGNOSTICS-v1-4b475242-4750-4812-9e53-f143c82f517a\n');files[marker]='/GBRUNCH-MEDIA.TXT'
readme=OUT/'README-FIRST.txt';readme.write_text('GBRUNCH HP diagnostic media. This does not start the Googlebook desktop.\nBoot option 1 provides a visible Linux console. Option 2 tests the unchanged Googlebook kernel.\nLogs are written only to this marked drive, under GBRUNCH-LOGS. Internal filesystems are not mounted.\nThe EFI loader is unsigned. Full recovery images must be downloaded separately from Google.\n');files[readme]='/README-FIRST.txt'
for source,dest in files.items():run(LOCAL/'usr/bin/mcopy','-o','-i',esp,source,'::'+dest)
total=258*1024*1024//512;first=2048;last=first+esp.stat().st_size//512-1
table=bytearray(16384);table[:16]=uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
table[16:32]=uuid.UUID('47504813-5242-4b47-9e53-f143c82f517a').bytes_le
struct.pack_into('<QQQ',table,32,first,last,0);name='GBRUNCH-HP-ESP'.encode('utf-16le');table[56:56+len(name)]=name
def header(current,backup,lba):
 h=bytearray(512);struct.pack_into('<8sIIIIQQQQ16sQIII',h,0,b'EFI PART',0x10000,92,0,0,current,backup,34,total-34,uuid.UUID('47504812-5242-4b47-9e53-f143c82f517a').bytes_le,lba,128,128,zlib.crc32(table));struct.pack_into('<I',h,16,zlib.crc32(h[:92]));return h
disk=OUT/'gbrunch-hp-diagnostics.img'
with disk.open('wb') as f:
 f.truncate(total*512);mbr=bytearray(512);mbr[446:462]=struct.pack('<B3sB3sII',0,b'\0\x02\0',0xee,b'\xff'*3,1,total-1);mbr[510:]=b'\x55\xaa';f.write(mbr);f.write(header(1,total-1,2));f.write(table);f.seek(first*512)
 with esp.open('rb') as src:
  while b:=src.read(1048576):f.write(b)
 f.seek((total-33)*512);f.write(table);f.write(header(total-1,1,total-33))
manifest={'purpose':'HP diagnostic disk, no Googlebook desktop/system partitions','disk_bytes':disk.stat().st_size,'disk_sha256':hashlib.sha256(disk.read_bytes()).hexdigest(),'google_kernel_sha256':hashlib.sha256(google_kernel.read_bytes()).hexdigest(),'linux_kernel_version':version,'linux_kernel_sha256':hashlib.sha256(linux_kernel.read_bytes()).hexdigest(),'linux_module_count':len(selected),'extra_module_targets':extra_names,'missing_extra_modules':[n for n in extra_names if n not in index],'cmdlines':{'linux':linux_cmd,'google':google_cmd},'log_write_gate':'GPT disk GUID and partition GUID and CRCs + FAT serial + marker; exactly one candidate','secure_boot':'unsigned experimental EFI loader','default':'full Linux batch then original Google kernel via kexec','full_android':'not included','firmware_services':'none; volatile Linux driver firmware loading only'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(OUT/'SHA256SUMS').write_text(manifest['disk_sha256']+'  '+disk.name+'\n');print(json.dumps(manifest,indent=2))
