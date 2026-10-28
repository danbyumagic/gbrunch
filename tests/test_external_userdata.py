import importlib.util,pathlib,struct,tempfile,unittest,zlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=module(ROOT/'tools/add_external_userdata.py','fresh')
g=module(ROOT/'prototypes/image-container/probe.py','probe')
class ExternalUserdataTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=pathlib.Path(self.tmp.name);a=p/'a';a.write_bytes(bytes(4096));g.gpt_image(p/'source',[('userdata',a),('super',a)]);b=(p/'source').read_bytes()[:17408];self.h=b[512:1024];self.t=b[1024:17408]
 def tearDown(self):self.tmp.cleanup()
 def test_only_userdata_moves_and_both_headers_validate(self):
  h,t,b=m.relocate(self.h,self.t,1000000,10000,50000)
  self.assertEqual(t[128:],self.t[128:]);self.assertEqual(struct.unpack_from('<QQ',t,32),(10000,59999))
  for header in (h,b):
   c=bytearray(header);expected=struct.unpack_from('<I',c,16)[0];struct.pack_into('<I',c,16,0);self.assertEqual(zlib.crc32(c[:92]),expected);self.assertEqual(zlib.crc32(t),struct.unpack_from('<I',c,88)[0])
 def test_corrupt_table_is_rejected(self):
  t=bytearray(self.t);t[150]^=1
  with self.assertRaises(ValueError):m.relocate(self.h,t,1000000,10000,50000)
 def test_overlap_rejected(self):
  with self.assertRaises(ValueError):m.relocate(self.h,self.t,1000000,2048,50000)
 def test_capacity_rejected(self):
  with self.assertRaises(ValueError):m.relocate(self.h,self.t,20000,10000,50000)
if __name__=='__main__':unittest.main()
