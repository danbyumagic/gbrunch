#!/usr/bin/env python3
"""Verify locally built USB payload, mount read-only, expose only a read-only loop."""
import pathlib,json,hashlib,subprocess,os,stat
from dualboot_installer import identity,require,COMPAT_HASH
M=pathlib.Path('/payload/SOURCE-MANIFEST.json')
def main():
 p=subprocess.check_output(['blkid','-L','GBPAYLOAD'],text=True).strip();require(bool(p),'No standalone payload')
 logs=subprocess.check_output(['blkid','-L','GBINSTALL'],text=True).strip()
 node=pathlib.Path('/sys/class/block')/pathlib.Path(p).name;ln=pathlib.Path('/sys/class/block')/pathlib.Path(logs).name
 require(node.resolve().parent==ln.resolve().parent,'Payload and logs must be on the same USB')
 require(identity('/dev/'+node.resolve().parent.name)['usb'],'Standalone payload must be on USB')
 pathlib.Path('/payload').mkdir(exist_ok=True)
 subprocess.run(['mount','-t','ext4','-o','ro,noload,nodev,nosuid,noexec',p,'/payload'],check=True)
 md=json.loads(M.read_text());require(md['format']=='GBRUNCH standalone source v1' and md['compat_sha256']==COMPAT_HASH,'Wrong payload profile')
 source=pathlib.Path('/payload/source.raw');ss=source.lstat();require(stat.S_ISREG(ss.st_mode) and ss.st_size==md['source_bytes'],'Source size/type mismatch')
 print('Verifying Googlebook payload before enabling installation. This can take several minutes.',flush=True)
 h=hashlib.sha256();done=0;nextprogress=0
 with source.open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):
   h.update(b);done+=len(b)
   if done>=nextprogress:print('Verified %.1f / %.1f GB'%(done/1e9,ss.st_size/1e9),flush=True);nextprogress=done+(1<<30)
 require(h.hexdigest()==md['source_sha256'],'Payload SHA256 mismatch. Installation disabled.')
 marker=dict(path=str(source),inode=ss.st_ino,device=ss.st_dev,bytes=ss.st_size,sha256=h.hexdigest(),manifest_sha256=hashlib.sha256(M.read_bytes()).hexdigest())
 pathlib.Path('/run/standalone-source-verified.json').write_text(json.dumps(marker))
 loop=subprocess.check_output(['losetup','--find','--show','--read-only',str(source)],text=True).strip()
 try:identity(loop)
 except Exception:
  subprocess.run(['losetup','-d',loop]);pathlib.Path('/run/standalone-source-verified.json').unlink();raise
 pathlib.Path('/logs/standalone-verification.json').write_text(json.dumps(dict(marker,loop=loop),indent=2)+'\n')
 print('Payload verified; source is read-only: '+loop,flush=True)
if __name__=='__main__':main()
