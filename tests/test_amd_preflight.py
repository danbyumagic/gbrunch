import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from build_amd_kernel_modules import config_values, forbidden_changes

class PlanAGuards(unittest.TestCase):
    def test_reject_new_builtins_and_changed_original_builtins(self):
        changes = forbidden_changes({'DRM':'y','AMD_IOMMU':'n'}, {'DRM':'m','AMD_IOMMU':'y'})
        self.assertEqual(set(changes), {'DRM','AMD_IOMMU'})
    def test_allow_modules_without_rewriting_core(self):
        self.assertEqual(forbidden_changes({'DRM':'y','DRM_AMDGPU':'n'}, {'DRM':'y','DRM_AMDGPU':'m'}), {})
    def test_unset_and_compiler_config(self):
        result = config_values('CONFIG_DRM=y\n# CONFIG_DRM_AMDGPU is not set\nCONFIG_CC_VERSION_TEXT="clang 22"\n')
        self.assertEqual(result['DRM_AMDGPU'], 'n')
        self.assertEqual(result['CC_VERSION_TEXT'], '"clang 22"')
if __name__ == '__main__': unittest.main()
