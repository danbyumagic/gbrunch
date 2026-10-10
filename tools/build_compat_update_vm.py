#!/usr/bin/env python3
"""Open-source update VM; source SSD read-only, generated Google bytes stay local."""
import gzip,pathlib,stat,json,hashlib
import build_local_tool_vm as base
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/compat-update-v3';O.mkdir(exist_ok=True)
base.entries.clear();base.origins.clear()
for name in ['compat_update_guest.py','native_vendor_in_vm.py','maintain_userdata_guest.py','inspect_recovery.py']:base.copy(R/'tools'/name,'payload/'+name)
base.copy(R/'build/check-graphics-memfd-policy','bin/check-graphics-memfd-policy',True);base.libs(R/'build/check-graphics-memfd-policy')
base.add('payload/modules.json',b'[]\n',stat.S_IFREG|0o644,'No hardware module extraction required by this patch')
script='''#!/bin/sh
export PATH=/bin:/usr/bin PYTHONHOME=/usr PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
while read module; do insmod /modules/$module; done < /etc/module-order
mdev -s
if mount -t vfat /dev/vda /work; then
 if [ "$(cat /work/GBRUNCH-BUILD-MARKER.txt)" = 'GBRUNCH local build-tool work disk' ]; then
  python3 /payload/compat_update_guest.py > /work/build-log.txt 2>&1
  code=$?
  echo $code > /work/status.txt
  cat /work/build-log.txt
  sync
 fi
 umount /work
fi
poweroff -f
'''
base.add('init',script.encode(),stat.S_IFREG|0o755,'Owned readonly-source update init')
cpio=b''.join(entry(n,b,mode,995000+i) for i,(n,(mode,b)) in enumerate(base.entries.items()))+entry('TRAILER!!!',b'',0,999900)
(O/'initrd.gz').write_bytes(gzip.compress(gzip.decompress((R/'build/local-tool-vm/initrd.gz').read_bytes())+cpio,mtime=0))
if not (O/'linux-kernel').exists():(O/'linux-kernel').hardlink_to(R/'build/local-tool-vm/linux-kernel')
(O/'runtime-manifest.json').write_text(json.dumps({'scope':'GPL/open-source tools only; no proprietary Google image bytes','added_files':base.origins},indent=2)+'\n')
print(O)
