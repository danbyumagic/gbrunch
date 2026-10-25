import hashlib,pathlib,sys,tempfile,types,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import assemble_native_android as assembler

class NativeRecoverySelection(unittest.TestCase):
    def test_explicit_profile_uses_its_hash_without_changing_legacy_pins(self):
        with tempfile.TemporaryDirectory() as td:
            source=pathlib.Path(td)/'new.raw';source.write_bytes(b'NEW RECOVERY FIXTURE')
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            args=types.SimpleNamespace(recovery_raw=source,profile={'raw_sha256':digest})
            previous=(assembler.URL,assembler.ZIP_HASH,assembler.RAW_HASH)
            self.assertEqual(assembler.recovery(args),source.resolve())
            self.assertEqual((assembler.URL,assembler.ZIP_HASH,assembler.RAW_HASH),previous)
            self.assertEqual(source.read_bytes(),b'NEW RECOVERY FIXTURE')

    def test_mismatched_profile_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as td:
            source=pathlib.Path(td)/'old.raw';source.write_bytes(b'KEEP OLD RECOVERY')
            args=types.SimpleNamespace(recovery_raw=source,profile={'raw_sha256':'0'*64})
            with self.assertRaisesRegex(ValueError,'raw recovery hash mismatch'):assembler.recovery(args)
            self.assertEqual(source.read_bytes(),b'KEEP OLD RECOVERY')
