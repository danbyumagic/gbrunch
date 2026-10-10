#!/usr/bin/env python3
"""Exercise real offset writes/readback/rollback on a disposable sparse file."""
import hashlib,importlib.util,json,pathlib,plistlib,subprocess,tempfile,unittest,os
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('updater',R/'tools/update_external_ssd_v4_macos.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
REAL_RUN=subprocess.run
META=dict(Internal=False,WholeDisk=True,DeviceNode='/dev/disk21',DeviceIdentifier='disk21',VirtualOrPhysical='Physical',SystemImage=False,DeviceBlockSize=512,TotalSize=128<<30,DeviceTreePath='fixture-usb-port')
class Check(unittest.TestCase):
 def exercise(self,fail):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);kit=root/'kit';kit.mkdir();disk=root/'disk.raw'
   with disk.open('wb') as f:
    f.truncate(128<<30);f.write(b'GPT fixture'.ljust(17408,b'\0'))
    for offset in [1<<20,65<<20,67<<20,70<<20]:f.seek(offset);f.write(b'original-data')
   protected={}
   with disk.open('rb') as f:
    for offset in [0,67<<20,70<<20]:f.seek(offset);protected[offset]=f.read(17408)
   compat=kit/'gbrunch-compat-v4.ext4'
   with compat.open('wb') as f:f.truncate(64<<20);f.write(b'new-compat')
   vendor=b'new-vendor'.ljust(1<<20,b'\0')
   parts=[dict(name='GBRUNCH',guid=m.GUIDS['GBRUNCH'],offset=1<<20,bytes=64<<20),dict(name='GBVENDOR',guid=m.GUIDS['GBVENDOR'],offset=65<<20,bytes=1<<20),dict(name='system',offset=67<<20,bytes=1<<20),dict(name='userdata',offset=70<<20,bytes=64<<30)]
   result=dict(partitions=parts,primary_gpt_sha256=hashlib.sha256(protected[0]).hexdigest(),source_ssd_readonly=True,graphics_av_checks_passed=True,vendor_bytes=len(vendor),vendor_sha256=hashlib.sha256(vendor).hexdigest())
   (kit/'asset-hashes.json').write_text(json.dumps({'gbrunch-compat-v4.ext4':m.sha256_file(compat)}));(kit/'request.json').write_text('{}')
   writes=[];injected=False
   def execute(cmd,**kwargs):
    nonlocal injected
    cmd=[str(a) for a in cmd]
    if cmd[0]=='diskutil':return subprocess.CompletedProcess(cmd,0)
    if cmd[0]=='mformat':return subprocess.CompletedProcess(cmd,0)
    if cmd[0]=='qemu':
     self.assertTrue(any('file=/dev/rdisk21,readonly=on' in a for a in cmd));return subprocess.CompletedProcess(cmd,0)
    if cmd[0]=='mcopy':
     name=next((a[3:] for a in cmd if a.startswith('::/') and a!='::/'),None)
     if name:
      payload={'status.txt':b'0\n','build-log.txt':b'fixture VM build','update-result.json':json.dumps(result).encode(),'policy-changes.txt':b'3 rules','policy-before.txt':b'denied','policy-after.txt':b'allowed','vendor.erofs':vendor}[name]
      pathlib.Path(cmd[-1]).write_bytes(payload)
     return subprocess.CompletedProcess(cmd,0)
    if cmd[0]=='dd':
     if 'of=/dev/rdisk21' in cmd:
      writes.append(cmd.copy())
      if fail and not injected and ('if='+str(compat)) in cmd:
       injected=True;raise subprocess.CalledProcessError(1,cmd)
     cmd=[a.replace('/dev/rdisk21',str(disk)).replace('bs=1m','bs=1M') for a in cmd]
    return REAL_RUN(cmd,**kwargs)
   argv=['update','--disk','/dev/disk21','--qemu','qemu','--mcopy','mcopy','--mformat','mformat','--work',str(root/'work')]
   with patch.object(m,'__file__',str(kit/'update.py')),patch.object(m.sys,'platform','darwin'),patch.object(m.sys,'argv',argv),patch.object(m.os,'geteuid',return_value=0),patch.object(m.subprocess,'check_output',return_value=plistlib.dumps(META)),patch.object(m.subprocess,'run',side_effect=execute):
    if fail:
     with self.assertRaises(SystemExit):m.main()
    else:m.main()
   with disk.open('rb') as f:
    for offset,value in protected.items():f.seek(offset);self.assertEqual(f.read(len(value)),value)
    f.seek(1<<20);self.assertEqual(f.read(13),b'original-data' if fail else b'new-compat\0\0\0')
    f.seek(65<<20);self.assertEqual(f.read(13),b'original-data' if fail else vendor[:13])
   allowed_seeks={'seek=1','seek=65'}
   self.assertTrue(all(any(x in cmd for x in allowed_seeks) for cmd in writes))
   status=json.loads((root/'work/host-status.json').read_text())
   self.assertEqual(status['phase'],'backups restored after failure' if fail else 'complete')
 def test_success(self):self.exercise(False)
 def test_write_failure_restores_both(self):self.exercise(True)
 def test_target_guards(self):
  result=dict(partitions=[dict(name='GBRUNCH',guid=m.GUIDS['GBRUNCH'],offset=1<<20,bytes=64<<20),dict(name='GBVENDOR',guid='wrong',offset=65<<20,bytes=1<<20)],source_ssd_readonly=True,graphics_av_checks_passed=True)
  with self.assertRaises(AssertionError):m.validate_targets(result,64<<20,1<<20)
if __name__=='__main__':unittest.main()
