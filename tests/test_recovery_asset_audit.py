import hashlib,pathlib,sys,types,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import audit_recovery_assets as audit

class AssetAuditTests(unittest.TestCase):
    def test_empty_success_does_not_hide_vendor_module(self):
        data=b'\x7fELF MODULE FIXTURE'
        outputs=[types.SimpleNamespace(returncode=0,stdout=b''),types.SimpleNamespace(returncode=0,stdout=data)]
        with patch.object(audit.subprocess,'run',side_effect=outputs) as run:
            result=audit.find_module('dump.erofs','private.raw','xe.ko',{'system_dlkm_a':1,'vendor_dlkm_a':2})
        self.assertEqual(run.call_count,2)
        self.assertEqual(result,{'source':'vendor_dlkm_a','actual_sha256':hashlib.sha256(data).hexdigest()})

    def test_nonelf_or_failed_output_is_not_a_module(self):
        outputs=[types.SimpleNamespace(returncode=0,stdout=b'NOT A MODULE'),types.SimpleNamespace(returncode=1,stdout=b'\x7fELF partial')]
        with patch.object(audit.subprocess,'run',side_effect=outputs):
            self.assertIsNone(audit.find_module('dump','private.raw','xe.ko',{'system_dlkm_a':1,'vendor_dlkm_a':2}))
