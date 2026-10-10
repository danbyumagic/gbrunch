#!/usr/bin/env python3
"""Open-source V7 assembly assets, excluding all Google-derived binaries."""
import pathlib,os,shutil,json,hashlib,gzip,stat
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];O=pathlib.Path('/tmp/gbrunch-standalone-assets');O.mkdir(exist_ok=True)
for p in (R/'build/native-assets').rglob('*'):
 if not p.is_file():continue
 dest=O/p.relative_to(R/'build/native-assets');dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():dest.unlink()
 shutil.copyfile(p,dest)
compat=O/'compat.ext4';compat.unlink();shutil.copyfile(R/'build/compat-wifi-v7/compat.ext4',compat)
init='''#!/bin/sh
export PATH=/bin:/usr/bin PYTHONHOME=/usr PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /run
while read module; do insmod /modules/$module 2>/dev/null || true; done < /etc/module-order
mdev -s
if mount -t vfat /dev/vda /work; then
 if [ "$(cat /work/GBRUNCH-BUILD-MARKER.txt)" = 'GBRUNCH local build-tool work disk' ]; then
  python3 /payload/native_vendor_in_vm.py > /work/build-log.txt 2>&1
  result=$?; echo $result > /work/status.txt; cat /work/build-log.txt; sync
 fi
 umount /work
fi
poweroff -f
'''
extra=entry('init',init.encode(),stat.S_IFREG|0o755,1500001)
for i,n in enumerate(['native_vendor_in_vm.py','graphics_client_domains.json']):extra+=entry('payload/'+n,(R/'tools'/n).read_bytes(),stat.S_IFREG|0o644,1500010+i)
extra+=entry('payload/modules.json',(R/'build/local-tool-vm/modules.json').read_bytes(),stat.S_IFREG|0o644,1500050)
extra+=entry('TRAILER!!!',b'',0,1500099)
p=O/'tool-initrd.gz';p.unlink();p.write_bytes(gzip.compress(gzip.decompress((R/'build/gbrunch-compat-v7-kit/initrd.gz').read_bytes())+extra,compresslevel=6,mtime=0))
for n in ['native_vendor_in_vm.py','graphics_client_domains.json','build_standalone_assets.py']:
 shutil.copyfile(R/'tools'/n,O/'rebuild-source'/n)
(O/'standalone-runtime-provenance.json').write_text(json.dumps(dict(base_v7_initrd_sha256=hashlib.sha256((R/'build/gbrunch-compat-v7-kit/initrd.gz').read_bytes()).hexdigest(),overlays={n:hashlib.sha256((R/'tools'/n).read_bytes()).hexdigest() for n in ['native_vendor_in_vm.py','graphics_client_domains.json']},module_metadata_sha256=hashlib.sha256((R/'build/local-tool-vm/modules.json').read_bytes()).hexdigest(),scope='GNU/AOSP tools only; module metadata refers to bytes extracted locally from the official recovery'),indent=2)+'\n')
m=json.loads((O/'native-assets.json').read_text());m['cmdline']=m['cmdline'].replace('drm.debug=0x1e','drm.debug=0');m['scope']='Open-source standalone V7 local builder; official recovery supplied locally'
m['files']={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and p.name!='native-assets.json'}
p=O/'native-assets.json';p.unlink();p.write_text(json.dumps(m,indent=2)+'\n');print(O)
