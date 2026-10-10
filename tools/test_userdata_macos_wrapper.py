#!/usr/bin/env python3
"""Check macOS identity rejection and the diagnostic read-only QEMU graph."""
import importlib.util,json,pathlib,plistlib,subprocess,tempfile,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).with_name('maintain_external_ssd_macos.py')
spec=importlib.util.spec_from_file_location('wrapper',P);wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
META=dict(Internal=False,WholeDisk=True,DeviceNode='/dev/disk21',DeviceIdentifier='disk21',VirtualOrPhysical='Physical',SystemImage=False,DeviceBlockSize=512,TotalSize=240057409536)
class Checks(unittest.TestCase):
 def test_identity(self):
  wrapper.validate_disk_identity(META,'/dev/disk21')
  for change in [{'Internal':True},{'WholeDisk':False},{'WholeDisk':None},{'VirtualOrPhysical':'Virtual'},{'VirtualOrPhysical':None},{'DeviceNode':'/dev/disk6'},{'DeviceIdentifier':'disk6'},{'SystemImage':True},{'DeviceBlockSize':4096},{'TotalSize':10}]:
   with self.subTest(change=change),self.assertRaises(ValueError):wrapper.validate_disk_identity(dict(META,**change),'/dev/disk21')
 def test_diagnostic_disk_graph(self):
  calls=[]
  def run(cmd,**kwargs):
   calls.append(cmd)
   return subprocess.CompletedProcess(cmd,0,stdout=b'0\n',stderr=b'')
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);assets=root/'kit';assets.mkdir();(assets/'asset-hashes.json').write_text('{}')
   argv=['wrapper','--disk','/dev/disk21','--action','diagnose','--qemu','qemu','--qemu-img','qemu-img','--mcopy','mcopy','--mformat','mformat','--work',str(root/'work')]
   with patch.object(wrapper,'__file__',str(assets/'wrapper.py')),patch.object(wrapper.sys,'platform','darwin'),patch.object(wrapper.sys,'argv',argv),patch.object(wrapper.os,'geteuid',return_value=0),patch.object(wrapper.subprocess,'check_output',return_value=plistlib.dumps(META)),patch.object(wrapper.subprocess,'run',side_effect=run):wrapper.main()
  cmd=next(c for c in calls if c[0]=='qemu')
  nodes=[json.loads(cmd[i+1]) for i,v in enumerate(cmd) if v=='-blockdev']
  self.assertEqual(len(nodes),4)
  self.assertEqual(nodes[0],dict(driver='host_device',filename='/dev/rdisk21',**{'node-name':'ssd-file','read-only':True}))
  self.assertTrue(nodes[1]['read-only'])
  self.assertEqual(nodes[3]['backing'],'ssd-source')
  self.assertEqual(cmd[-2:],['-device','virtio-blk-pci,drive=disk'])
  self.assertIn('gbrunch.userdata_overlay=1',cmd[cmd.index('-append')+1])
  self.assertFalse(any('file=/dev/rdisk' in arg for arg in cmd))
if __name__=='__main__':unittest.main()
