import pathlib
import gzip
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from build_amd_kernel_modules import config_values, forbidden_changes, verify_embedded_config

class PlanAGuards(unittest.TestCase):
    def test_reject_new_builtins_and_changed_original_builtins(self):
        changes = forbidden_changes({'DRM':'y','AMD_IOMMU':'n'}, {'DRM':'m','AMD_IOMMU':'y'})
        self.assertEqual(set(changes), {'DRM','AMD_IOMMU'})
    def test_allow_modules_without_rewriting_core(self):
        self.assertEqual(forbidden_changes({'DRM':'y','DRM_AMDGPU':'n'}, {'DRM':'y','DRM_AMDGPU':'m'}), {})
    def test_exception_requires_modular_amdgpu(self):
        before = {'DRM_AMD_DC':'n', 'DRM_AMD_DC_FP':'n'}
        after = {'DRM_AMDGPU':'m', 'DRM_AMD_DC':'y', 'DRM_AMD_DC_FP':'y'}
        self.assertEqual(forbidden_changes(before, after, True), {})
        after['DRM_AMDGPU'] = 'y'
        self.assertIn('DRM_AMD_DC', forbidden_changes(before, after, True))
    def test_exception_does_not_allow_other_core_booleans(self):
        self.assertIn('SYSFB_SIMPLEFB', forbidden_changes({}, {'SYSFB_SIMPLEFB':'y'}, True))
    def test_recovery_config_mismatch_is_rejected(self):
        config = 'CONFIG_DRM=y\n'
        kernel = b'ELF' + b'IKCFG_ST' + gzip.compress(config.encode()) + b'IKCFG_ED'
        verify_embedded_config(kernel, config)
        with self.assertRaises(ValueError):
            verify_embedded_config(kernel, 'CONFIG_DRM=m\n')
        with self.assertRaises(ValueError):
            verify_embedded_config(b'no-config', config)
    def test_platform_bool_cannot_use_display_exception(self):
        for option in ('PINCTRL_AMD', 'X86_AMD_PLATFORM_DEVICE', 'AMD_IOMMU'):
            self.assertIn(option, forbidden_changes({}, {option:'y', 'DRM_AMDGPU':'m'}, True))
    def test_unset_and_compiler_config(self):
        result = config_values('CONFIG_DRM=y\n# CONFIG_DRM_AMDGPU is not set\nCONFIG_CC_VERSION_TEXT="clang 22"\n')
        self.assertEqual(result['DRM_AMDGPU'], 'n')
        self.assertEqual(result['CC_VERSION_TEXT'], '"clang 22"')
if __name__ == '__main__': unittest.main()
