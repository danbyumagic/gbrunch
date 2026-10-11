#!/usr/bin/env python3
"""File-only Cuttlefish x86 kernel/virtio GPU probe; does not boot Googlebook."""
import argparse, gzip, os, pathlib, subprocess
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--donor', required=True, type=pathlib.Path)
p.add_argument('--busybox', required=True, type=pathlib.Path)
p.add_argument('--qemu', required=True, type=pathlib.Path)
p.add_argument('--work', required=True, type=pathlib.Path)
p.add_argument('--qemu-data', type=pathlib.Path)
p.add_argument('--bios', type=pathlib.Path)
a = p.parse_args()
a.work.mkdir(parents=True, exist_ok=True)
out = bytearray()
def entry(name, data, mode, major=0, minor=0):
    name = name.encode()+b'\0'
    fields = [1,mode,0,0,1,0,len(data),0,0,major,minor,len(name),0]
    out.extend(b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name)
    out.extend(b'\0'*(-len(out)%4)); out.extend(data); out.extend(b'\0'*(-len(out)%4))
for directory in ['dev','proc','sys','modules','bin']:
    entry(directory,b'',0o40755)
entry('dev/console',b'',0o20600,5,1)
entry('bin/busybox',a.busybox.read_bytes(),0o100755)
mods=['virtio_pci_legacy_dev','virtio_pci_modern_dev','virtio_pci','virtio_dma_buf','virtio-gpu','virtio_input','virtio_console']
base=a.donor/'vendor_boot/fragment-0-platform-files/lib/modules'
for m in mods: entry('modules/'+m+'.ko',(base/(m+'.ko')).read_bytes(),0o100644)
init='''#!/bin/busybox sh
export PATH=/bin
/bin/busybox --install -s /bin
/bin/busybox mount -t proc proc /proc
/bin/busybox mount -t sysfs sysfs /sys
/bin/busybox mount -t devtmpfs devtmpfs /dev
/bin/busybox uname -a
'''
for m in mods: init+=f'/bin/busybox insmod /modules/{m}.ko || echo MODULE_LOAD_FAILED:{m}\n'
init+='''/bin/busybox mknod /dev/hvc0 c 229 0
exec >/dev/hvc0 2>&1
/bin/busybox sleep 3
/bin/busybox ls -l /dev/dri
/bin/busybox ls -l /sys/class/drm
if [ -e /sys/class/drm/card0/dev ] && [ -e /sys/class/drm/renderD128/dev ]; then echo VIRTIO_GPU_PROBE_PASS; else echo VIRTIO_GPU_PROBE_FAIL; fi
/bin/busybox dmesg
/bin/busybox poweroff -f
'''
entry('init',init.encode(),0o100755); entry('TRAILER!!!',b'',0)
ramdisk=a.work/'probe-initrd.gz'; ramdisk.write_bytes(gzip.compress(out,mtime=0))
cmd=[str(a.qemu.resolve()),'-machine','q35','-accel','tcg','-cpu','max','-m','1024','-smp','2','-kernel',str((a.donor/'boot/kernel').resolve()),'-initrd',str(ramdisk.resolve()),'-append','console=ttyS0,115200 earlycon=uart8250,io,0x3f8 nokaslr rdinit=/init panic=-1','-vga','none','-device','virtio-gpu-pci,romfile=','-display','none','-serial','none','-device','virtio-serial-pci','-chardev','stdio,id=console','-device','virtconsole,chardev=console','-monitor','none','-nic','none','-no-reboot']
if a.qemu_data: cmd+=['-L',str(a.qemu_data.resolve())]
if a.bios: cmd+=['-bios',str(a.bios.resolve())]
log=a.work/'serial.log'
with log.open('wb') as f:
    try: result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=120)
    except subprocess.TimeoutExpired: raise SystemExit(f'Probe timed out; inspect {log}')
text=log.read_text(errors='replace')
passed=result.returncode==0 and 'VIRTIO_GPU_PROBE_PASS' in text and 'MODULE_LOAD_FAILED:' not in text
print(f'{"PASS" if passed else "FAIL"}: {log}')
raise SystemExit(0 if passed else 1)
