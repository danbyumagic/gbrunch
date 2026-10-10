#!/usr/bin/env python3
"""Add e2fs tools and a bounded-loop maintenance helper to the open-source VM."""
import gzip,pathlib,os,lzma,stat,json,hashlib,subprocess,shutil
import build_local_tool_vm as base
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/userdata-maintenance';O.mkdir(exist_ok=True)
base.entries.clear();base.origins.clear()
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
for name in ['e2fsck','resize2fs','dumpe2fs','debugfs','mke2fs']:
    p=R/'tools/local/usr/sbin'/name;base.copy(p,'bin/'+name,True);base.libs(p,env)
base.copy(R/'tools/local/etc/mke2fs.conf','etc/mke2fs.conf')
base.copy(R/'tools/maintain_userdata_guest.py','payload/maintain_userdata_guest.py')
base.copy(R/'tools/inspect_recovery.py','payload/inspect_recovery.py')
p=next((R/'tools/hp-kernel/usr/lib/modules').glob('*/kernel/drivers/block/loop.ko.xz'))
base.add('modules/loop.ko',lzma.decompress(p.read_bytes()),stat.S_IFREG|0o644,p)
script='''#!/bin/sh
export PATH=/bin:/usr/bin
export PYTHONHOME=/usr
export PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /run
while read module; do insmod /modules/$module || echo MODULE_FAILED:$module; done < /etc/module-order
insmod /modules/loop.ko || echo LOOP_MODULE_FAILED
mdev -s
if mount -t vfat /dev/vda /work; then
 if [ "$(cat /work/GBRUNCH-USERDATA-MARKER.txt)" = 'GBRUNCH isolated userdata maintenance' ]; then
  python3 /payload/maintain_userdata_guest.py > /work/maintenance-log.txt 2>&1
  code=$?
  echo $code > /work/status.txt
  cat /work/maintenance-log.txt
  sync
 fi
 umount /work
fi
poweroff -f
'''
base.add('init',script.encode(),stat.S_IFREG|0o755,'owned offline maintenance init')
extra=b''.join(entry(n,b,mode,990000+i) for i,(n,(mode,b)) in enumerate(base.entries.items()))+entry('TRAILER!!!',b'',0,999999)
raw=gzip.decompress((R/'build/local-tool-vm/initrd.gz').read_bytes())
(O/'initrd.gz').write_bytes(gzip.compress(raw+extra,mtime=0))
kernel=O/'linux-kernel'
if not kernel.exists():kernel.hardlink_to(R/'build/local-tool-vm/linux-kernel')
(O/'runtime-manifest.json').write_text(json.dumps({'scope':'open-source tools; no Google OS bytes','added_files':base.origins,
 'initrd_sha256':hashlib.sha256((O/'initrd.gz').read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest()},indent=2)+'\n')
print(O)
