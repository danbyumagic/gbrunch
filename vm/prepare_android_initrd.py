#!/usr/bin/env python3
"""Assemble a private experimental ramdisk from local recovery/donor files."""
import argparse,gzip,pathlib
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--ruby',required=True,type=pathlib.Path)
p.add_argument('--donor',required=True,type=pathlib.Path)
p.add_argument('--fstab',required=True,type=pathlib.Path)
p.add_argument('--compat-init',required=True,type=pathlib.Path,help='Project-owned compatibility init.rc, not a vendor image')
p.add_argument('--with-system-heap',action='store_true',help='Include matching donor DMA heap module and dependency entry')
p.add_argument('--skip-shader-prewarm',action='store_true',help='Experimental: disable optional SurfaceFlinger shader prewarming in the owned VM init sidecar')
p.add_argument('--skip-ai-preloads',action='store_true',help='Experimental: omit the optional AICore model copy; local AI remains unverified')
p.add_argument('--output',required=True,type=pathlib.Path)
a=p.parse_args()
if a.output.exists(): p.error('Output already exists; choose a fresh path')
data=bytearray((a.donor/'vendor_boot/fragment-0-platform.cpio').read_bytes())
data.extend((a.ruby/'init_boot_a/ramdisk.cpio').read_bytes())
def append(name,body):
    name=name.encode()+b'\0'
    fields=[900000,0o100644,0,0,1,0,len(body),0,0,0,0,len(name),0]
    block=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)+name
    block+=b'\0'*(-len(block)%4);block+=body;block+=b'\0'*(-len(block)%4)
    data.extend(block)
mods=['virtio_pci_legacy_dev','virtio_pci_modern_dev','virtio_pci','virtio_dma_buf','virtio-gpu','virtio_input','virtio_console']
if a.with_system_heap:
    mods.append('system_heap')
    append('lib/modules/system_heap.ko',(a.donor/'vendor_dlkm-files/lib/modules/system_heap.ko').read_bytes())
    append('lib/modules/modules.dep',(a.donor/'vendor_boot/fragment-0-platform-files/lib/modules/modules.dep').read_bytes()+b'\n/lib/modules/system_heap.ko:\n')
append('lib/modules/modules.load',(''.join(m+'.ko\n' for m in mods)).encode())
append('first_stage_ramdisk/fstab.android-desktop',a.fstab.read_bytes())
# Explicit VM init entry removes physical Intel module loading. Original system
# and vendor imports remain; this is not a complete virtual vendor conversion.
rc=a.compat_init.read_text()
rc='\n'.join(line for line in rc.splitlines() if not line.strip().startswith('insmod '))+'\n'
if a.skip_shader_prewarm:
    rc+='\non init\n    setprop service.sf.prime_shader_cache 0\n'
a.output.parent.mkdir(parents=True,exist_ok=True)
rc_output=a.output.with_suffix('.vm-init.rc')
if rc_output.exists(): p.error('VM init sidecar already exists')
if a.skip_ai_preloads:
    original='import /system/etc/init/cppreopts.rc'
    if original not in rc:p.error('Compatibility init must import cppreopts.rc before this option can replace it')
    preopts_output=a.output.with_suffix('.vm-preopts.rc')
    if preopts_output.exists():p.error('VM preoptimization sidecar already exists')
    rc=rc.replace(original,'import /oem/vm-cppreopts.rc')
    preopts_output.write_text((pathlib.Path(__file__).parent/'experiments/vm-cppreopts-no-models.rc').read_text())
    print(f'Install {preopts_output} as /oem/vm-cppreopts.rc. AICore models will not be preloaded.')
rc_output.write_text(rc)
append('TRAILER!!!',b'')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_bytes(gzip.compress(data,mtime=0))
print(f'Created private local ramdisk: {a.output}')
print('Install the VM init sidecar into a private compatibility partition, then use androidboot.init_rc=/oem/init.gbrunch-vm.rc.')
