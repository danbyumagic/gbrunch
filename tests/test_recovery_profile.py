import hashlib,importlib.util,json,pathlib,tempfile,unittest,zipfile
spec=importlib.util.spec_from_file_location('recovery_profile',pathlib.Path(__file__).resolve().parents[1]/'tools/prepare_recovery_profile.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RecoveryProfileTests(unittest.TestCase):
    def fixture(self,root):
        payload=b'\0'*(1<<20)+b'RECOVERY FIXTURE'+b'\0'*123
        archive=root/'recovery.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('image.bin',payload)
        return payload,dict(device='ruby',build=16658739,url='https://dl.google.com/device/recovery/ruby-user/16658739/recovery.zip',zip_sha256=m.sha(archive),raw_sha256=hashlib.sha256(payload).hexdigest(),raw_bytes=len(payload))

    def test_sparse_extraction_and_verified_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);payload,p=self.fixture(root)
            raw=m.prepare(p,root)
            self.assertEqual(raw.read_bytes(),payload)
            self.assertEqual(m.prepare(p,root),raw)
            raw.write_bytes(b'WRONG')
            with self.assertRaisesRegex(ValueError,'Existing raw'):m.prepare(p,root)
            self.assertEqual(raw.read_bytes(),b'WRONG')

    def test_wrong_archive_never_extracts(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);_,p=self.fixture(root);p['zip_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'Archive SHA256'):m.prepare(p,root)
            self.assertFalse((root/'recovery.raw').exists())

    def test_symlink_destination_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);_,p=self.fixture(root)
            protected=root/'important';protected.write_text('KEEP')
            (root/'recovery.raw').symlink_to(protected)
            with self.assertRaisesRegex(ValueError,'symlink'):m.prepare(p,root)
            self.assertEqual(protected.read_text(),'KEEP')

    def test_nonofficial_profile_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);_,p=self.fixture(root);p['url']='https://example.com/recovery.zip'
            file=root/'profile.json';file.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'official'):m.load_profile(file)
