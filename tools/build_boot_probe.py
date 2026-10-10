#!/usr/bin/env python3
"""Build a local-only GPT/UEFI boot probe using the untouched recovery kernel.

This is not a Googlebook userspace image. No target disks are opened for writing.
Only regular outputs below this workspace are accepted. Host root not required.
"""
import gzip, hashlib, json, os, pathlib, struct, subprocess, uuid, zlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT/'build/boot-probe'
OUT.mkdir(parents=True, exist_ok=True)
for p in (OUT, OUT/'esp.fat', OUT/'gbrunch-boot-probe.img'):
    assert p.resolve().is_relative_to(ROOT)
    assert not p.is_symlink()
    assert not p.exists() or p.is_dir() or p.is_file()
LOCAL = ROOT/'tools/local'
env = os.environ.copy()
env['LD_LIBRARY_PATH'] = str(LOCAL/'usr/lib/x86_64-linux-gnu')
env['PATH'] = str(LOCAL/'usr/bin')+':'+str(LOCAL/'usr/sbin')+':'+env['PATH']
def run(*args): subprocess.run([str(x) for x in args], env=env, check=True)
entries = []
def add(name, mode, data=b'', major=0, minor=0):
    n = name.encode()+b'\0'
    fields = [len(entries)+1, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(n), 0]
    h = b'070701'+b''.join(f'{x:08x}'.encode() for x in fields)
    x = h+n; x += bytes(-len(x)%4); x += data; x += bytes(-len(data)%4)
    entries.append(x)
for d in ['bin', 'dev', 'proc', 'sys', 'tmp', 'run', 'etc', 'modules']:
    add(d, 0o040755)
busybox = (LOCAL/'usr/bin/busybox').read_bytes()
add('bin/busybox', 0o100755, busybox)
for app in ['sh', 'mount', 'mkdir', 'cat', 'echo', 'ls', 'sleep', 'poweroff', 'uname', 'readlink', 'dmesg', 'insmod']:
    add('bin/'+app, 0o120777, b'busybox')
add('dev/console', 0o020600, major=5, minor=1)
add('dev/null', 0o020666, major=1, minor=3)
module_names = ['virtio_pci_modern_dev', 'virtio_pci_legacy_dev', 'virtio_pci', 'virtio_blk']
for name in module_names:
    add('modules/'+name+'.ko', 0o100644,
        (ROOT/'extracted/ruby/system_dlkm_a-files/lib/modules'/f'{name}.ko').read_bytes())
init = '''#!/bin/sh
export PATH=/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /tmp
mount -t tmpfs tmpfs /run
echo GBRUNCH_BOOT_PROBE_STARTED
uname -a
echo 'READ-ONLY PROBE: no block filesystem mounts, no firmware tools, no Android services.'
for name in virtio_pci_modern_dev virtio_pci_legacy_dev virtio_pci virtio_blk; do
    insmod /modules/$name.ko || { echo GBRUNCH_MODULE_LOAD_FAILED_$name; poweroff -f; }
done
echo GBRUNCH_STOCK_MODULES_LOADED
echo 'PCI inventory (ID, subsystem, bound driver):'
for d in /sys/bus/pci/devices/*; do
    echo "$d"
    cat "$d/vendor" "$d/device" "$d/subsystem_vendor" "$d/subsystem_device"
    readlink "$d/driver"
done
echo 'Block-device sysfs inventory:'
ls -l /sys/class/block
echo 'ACPI IDs:'
for d in /sys/bus/acpi/devices/*; do
    [ -f "$d/hid" ] && cat "$d/hid"
done
echo GBRUNCH_BOOT_PROBE_COMPLETE
sleep 5
poweroff -f
while true; do sleep 60; done
'''
add('init', 0o100755, init.encode())
add('TRAILER!!!', 0)
cpio = b''.join(entries)
(OUT/'initrd.cpio.gz').write_bytes(gzip.compress(cpio, mtime=0))
cmdline = 'rdinit=/init console=ttyS0,115200 earlycon=uart8250,io,0x3f8,115200 8250.nr_uarts=4 loglevel=6 panic=0'
cfg = f'''serial --unit=0 --speed=115200
terminal_output console serial
set timeout=0
menuentry "GBRUNCH read-only kernel probe (serial output)" {{
 linux /kernel {cmdline}
 initrd /initrd.cpio.gz
}}
'''
(OUT/'grub.cfg').write_text(cfg)
kernel = ROOT/'extracted/ruby/boot_a/kernel'
run(LOCAL/'usr/bin/grub-mkstandalone', '-O', 'x86_64-efi',
    '-d', LOCAL/'usr/lib/grub/x86_64-efi', '--fonts=', '--locales=',
    '-o', OUT/'BOOTX64.EFI', f'boot/grub/grub.cfg={OUT}/grub.cfg',
    f'kernel={kernel}', f'initrd.cpio.gz={OUT}/initrd.cpio.gz')
esp = OUT/'esp.fat'
with esp.open('wb') as f: f.truncate(128*1024*1024)
run(LOCAL/'usr/sbin/mkfs.fat', '-F', '32', '-i', '47425231', '-n', 'GBRUNCH', esp)
run(LOCAL/'usr/bin/mmd', '-i', esp, '::/EFI', '::/EFI/BOOT')
run(LOCAL/'usr/bin/mcopy', '-i', esp, OUT/'BOOTX64.EFI', '::/EFI/BOOT/BOOTX64.EFI')
run(LOCAL/'usr/bin/mcopy', '-i', esp, kernel, '::/kernel')
run(LOCAL/'usr/bin/mcopy', '-i', esp, OUT/'initrd.cpio.gz', '::/initrd.cpio.gz')
# One EFI System Partition; both GPT headers and tables; fixed UUIDs for reproducibility.
total = 130*1024*1024//512
first, last = 2048, 2048+esp.stat().st_size//512-1
table = bytearray(128*128)
table[:16] = uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
table[16:32] = uuid.UUID('a7a8d568-e53b-4e8c-bd00-531a480596ac').bytes_le
struct.pack_into('<QQQ', table, 32, first, last, 0)
label = 'GBRUNCH-ESP'.encode('utf-16le'); table[56:56+len(label)] = label
def header(current, backup, entries_lba):
    h = bytearray(512)
    struct.pack_into('<8sIIIIQQQQ16sQIII', h, 0, b'EFI PART', 0x10000, 92, 0, 0,
        current, backup, 34, total-34, uuid.UUID('b25b03c9-8e28-4c75-829e-8d8d455fbb18').bytes_le,
        entries_lba, 128, 128, zlib.crc32(table))
    struct.pack_into('<I', h, 16, zlib.crc32(h[:92])); return h
disk = OUT/'gbrunch-boot-probe.img'
with disk.open('wb') as f:
    f.truncate(total*512)
    mbr = bytearray(512); mbr[446:462] = struct.pack('<B3sB3sII', 0, b'\0\x02\0', 0xee, b'\xff'*3, 1, total-1); mbr[510:] = b'\x55\xaa'
    f.write(mbr); f.write(header(1, total-1, 2)); f.write(table)
    f.seek(first*512)
    with esp.open('rb') as src:
        while chunk := src.read(1024*1024): f.write(chunk)
    f.seek((total-33)*512); f.write(table); f.write(header(total-1, 1, total-33))
manifest = {'purpose': 'serial-console read-only kernel probe, not Googlebook userspace',
    'kernel_sha256': hashlib.sha256(kernel.read_bytes()).hexdigest(), 'cmdline': cmdline,
    'secure_boot': 'unsigned experimental loader; not tested with Secure Boot',
    'disk_bytes': disk.stat().st_size,
    'disk_sha256': hashlib.sha256(disk.read_bytes()).hexdigest()}
(OUT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps(manifest, indent=2))
