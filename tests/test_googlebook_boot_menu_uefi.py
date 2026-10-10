#!/usr/bin/env python3
"""Actual GRUB/SMBIOS admission and original-kernel handoff, file-only QEMU.
Requires a PRIVATE fixture FAT containing /EFI/GBRUNCH/kernel and initrd.gz.
No Google bytes or device logs are bundled or copied into the repository.
"""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from googlebook_boot_menu import render
p=argparse.ArgumentParser(description=__doc__)
for name in ['qemu','qemu-share','firmware','grub','mcopy','fixture','output']:p.add_argument('--'+name,required=True,type=pathlib.Path)
p.add_argument("--grub-modules",type=pathlib.Path)
a=p.parse_args()
results=[]
with tempfile.TemporaryDirectory(prefix='gbrunch-menu-qemu-') as temp:
 t=pathlib.Path(temp);efi=t/'disk/EFI/BOOT';efi.mkdir(parents=True)
 for name in ['kernel','initrd.gz']:
  subprocess.run([str(a.mcopy),'-i',str(a.fixture),'::/EFI/GBRUNCH/'+name,str(t/name)],check=True)
 kernel_sha=hashlib.sha256((t/'kernel').read_bytes()).hexdigest()
 assert kernel_sha=='7816c5d5b3500093e597b7362ecab103d5a32141b100d3eb7a8b33221fce7f41','Wrong private fixture kernel'
 cmd='rdinit=/init console=ttyS0,115200 loglevel=8 earlycon=uart8250,io,0x3f8,115200 panic=0 androidboot.init_rc=/oem/init.gbrunch.rc androidboot.boot_part_uuid=12345678-1234-1234-1234-123456789abc'
 for name,entry,vendor,product,board,boot in [
   ('dell-default-refused',0,'Dell Inc.','Test Latitude','Test Board',False),
   ('dell-experimental-handoff',1,'Dell Inc.','Test Latitude','Test Board',True),
   ('hp-default-handoff',0,'HP','HP Envy x360 2-in-1 Laptop 15-fe1xxx','8C4F',True),
   ('qemu-default-handoff',0,'QEMU','Standard PC','Test Board',True)]:
  # Test-only automatic menu selection and memdisk paths; production arguments
  # are separately checked by test_googlebook_boot_menu.py.
  cfg='set root=(memdisk)\n'+render(cmd).replace('set timeout=10','set timeout=1',1).replace('set default=0','set default='+str(entry),1)
  (t/'grub.cfg').write_text(cfg)
  subprocess.run([str(a.grub)]+(['-d',str(a.grub_modules)] if a.grub_modules else [])+['-O','x86_64-efi','--locales=','--fonts=','-o',str(efi/'BOOTX64.EFI'),'boot/grub/grub.cfg='+str(t/'grub.cfg'),'EFI/GBRUNCH/kernel='+str(t/'kernel'),'EFI/GBRUNCH/initrd.gz='+str(t/'initrd.gz')],check=True)
  shutil.copy2(a.firmware/'OVMF_VARS_4M.fd',t/'vars.fd')
  log=t/(name+'.log');err=t/(name+'.stderr')
  args=[str(a.qemu),'-L',str(a.qemu_share),'-machine','q35','-accel','tcg','-cpu','max','-m','1024','-smp','2','-display','none','-vga','none','-monitor','none','-serial','file:'+str(log),'-net','none','-no-reboot','-drive','if=pflash,format=raw,readonly=on,file='+str(a.firmware/'OVMF_CODE_4M.fd'),'-drive','if=pflash,format=raw,file='+str(t/'vars.fd'),'-drive','format=raw,file=fat:rw:'+str(t/'disk'),'-smbios','type=1,manufacturer='+vendor+',product='+product,'-smbios','type=2,manufacturer='+vendor+',product='+board]
  with err.open('wb') as stderr:
   vm=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=stderr)
   try:
    deadline=time.monotonic()+45;needle='Linux version 6.18.21' if boot else 'This default entry requires the tested HP'
    while time.monotonic()<deadline:
     text=log.read_text(errors='replace') if log.exists() else ''
     if needle in text:break
     if vm.poll() is not None:raise RuntimeError(name+' VM exited: '+err.read_text())
     time.sleep(.25)
    else:raise RuntimeError(name+' missing result: '+log.read_text(errors='replace')[-1600:])
    if not boot:assert 'Linux version' not in text
    results.append(dict(case=name,passed=True,original_kernel_handoff=boot))
    print(name+' PASS',flush=True)
   finally:
    if vm.poll() is None:vm.terminate()
    vm.wait(timeout=15)
a.output.write_text(json.dumps(dict(passed=True,kernel_sha256=kernel_sha,cases=results,scope='Actual GRUB in QEMU with simulated Dell/HP SMBIOS; test fixture initramfs, original Google kernel; no physical Dell or Android desktop claim'),indent=2)+'\n')
