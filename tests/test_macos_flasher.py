import pathlib,importlib.util,tempfile,unittest,gzip,hashlib
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load(ROOT/'macos/flash_external_ssd.py','flash');g=load(ROOT/'prototypes/image-container/probe.py','probe')
class MacFlashTests(unittest.TestCase):
 def info(self):return dict(DeviceIdentifier='disk21',WholeDisk=True,Internal=False,VirtualOrPhysical='Physical',DeviceBlockSize=512,TotalSize=240000000000,MediaReadOnly=False,Writable=True,DeviceTreePath='fixture-usb-port',MediaName='Fixture SSD',Removable=False)
 def test_external_fixed_ssd_allowed(self):self.assertEqual(m.check_target(self.info(),37000000000)['DeviceIdentifier'],'disk21')
 def test_internal_partition_virtual_small_readonly_and_unknown_rejected(self):
  for k,v in [('Internal',True),('WholeDisk',False),('VirtualOrPhysical','Virtual'),('TotalSize',32000000000),('Writable',False),('DeviceBlockSize',4096),('DeviceTreePath',''),('DeviceIdentifier','disk21s1')]:
   with self.subTest(k=k):
    d=self.info();d[k]=v
    with self.assertRaises(ValueError):m.check_target(d,37000000000)
 def test_gzip_stream_and_complete_gpt(self):
  with tempfile.TemporaryDirectory() as td:
   d=pathlib.Path(td);payload=d/'p';payload.write_bytes(b'fixture'*100);raw=d/'os.img';g.gpt_image(raw,[(n,payload) for n in ['userdata','super','GBRUNCH','GBVENDOR','GBLOG','EFI-SYSTEM']]);b=raw.read_bytes();z=d/'os.img.gz';z.write_bytes(gzip.compress(b));sha=hashlib.sha256(z.read_bytes()).hexdigest();size,digest,n=m.inspect_image(z,sha)
   self.assertEqual(size,len(b));self.assertEqual(digest,hashlib.sha256(b).hexdigest());self.assertEqual(n,6)
   damaged=bytearray(b[:1<<20]);damaged[600]^=1
   with self.assertRaises(ValueError):m.validate_gpt(bytes(damaged),b[-(1<<20):],len(b))
   with self.assertRaises(ValueError):m.inspect_image(z,'0'*64)
 def test_official_recovery_without_compatibility_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d=pathlib.Path(td);p=d/'p';p.write_bytes(b'x');raw=d/'official.img';g.gpt_image(raw,[('userdata',p),('super',p)]);b=raw.read_bytes()
   with self.assertRaises(ValueError):m.validate_gpt(b[:1<<20],b[-(1<<20):],len(b))
 def test_apfs_source_resolves_to_its_physical_store(self):
  records={'/dev/disk3s5':{'ParentWholeDisk':'disk3','APFSContainerReference':'disk3'},'/dev/disk3':{'DeviceIdentifier':'disk3','WholeDisk':True,'VirtualOrPhysical':'Virtual'},'/dev/disk0s2':{'ParentWholeDisk':'disk0'},'/dev/disk0':{'WholeDisk':True,'VirtualOrPhysical':'Physical','DeviceIdentifier':'disk0'}}
  containers={'Containers':[{'ContainerReference':'disk3','PhysicalStores':[{'DeviceIdentifier':'disk0s2'}]}]}
  with patch.object(m,'disk_info',side_effect=lambda dev:records[dev]),patch.object(m,'plist',return_value=containers),patch.object(m.subprocess,'check_output',return_value='Filesystem blocks used available capacity mounted\n/dev/disk3s5 1 1 1 1% /System/Volumes/Data\n'):
   self.assertEqual(m.source_physical_disks(pathlib.Path('/Users/test/image.gz')),{'disk0'})
 def test_apfs_snapshot_without_parent_key_resolves(self):
  records={'/dev/disk3s1s1':{'DeviceIdentifier':'disk3s1s1','APFSContainerReference':'disk3'},'/dev/disk3':{'DeviceIdentifier':'disk3','WholeDisk':True,'VirtualOrPhysical':'Virtual'},'/dev/disk0':{'DeviceIdentifier':'disk0','WholeDisk':True,'VirtualOrPhysical':'Physical'}}
  containers={'Containers':[{'ContainerReference':'disk3','PhysicalStores':[{'DeviceIdentifier':'disk0s2'}]}]}
  with patch.object(m,'disk_info',side_effect=lambda dev:records[dev]),patch.object(m,'plist',return_value=containers),patch.object(m.subprocess,'check_output',return_value='Filesystem blocks used available capacity mounted\n/dev/disk3s1s1 1 1 1 1% /\n'):
   self.assertEqual(m.source_physical_disks(pathlib.Path('/')),{'disk0'})
 def test_whole_device_requires_verified_whole_disk(self):
  for record in ({'DeviceIdentifier':'disk0','WholeDisk':False},{'DeviceIdentifier':'disk1','WholeDisk':True}):
   with patch.object(m,'disk_info',return_value=record):
    with self.assertRaises(ValueError):m.whole_device('disk0s2')
if __name__=='__main__':unittest.main()
