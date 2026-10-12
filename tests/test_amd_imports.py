import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from audit_amd_imports import classify
from build_amd_driver_objects import auto_config
from build_amd_replacement_kernel import apply_options, OVERRIDES
from build_amd_kernel_modules import config_values

class ImportAudit(unittest.TestCase):
    def test_module_provider_is_not_missing_core_symbol(self):
        result = classify({'core_fn','helper_fn','missing_fn'}, {'core_fn'}, {'helper_fn':['helper.ko']})
        self.assertEqual(result['missing'], ['missing_fn'])
        self.assertEqual(result['module_providers'], {'helper_fn':['helper.ko']})
    def test_replacement_enables_real_amd_platform_support(self):
        config = apply_options('CONFIG_CPU_SUP_AMD=y\n# CONFIG_PINCTRL_AMD is not set\n', OVERRIDES)
        values = config_values(config)
        self.assertEqual(values['PINCTRL_AMD'], 'y')
        self.assertEqual(values['AMD_IOMMU'], 'y')
        self.assertEqual(values['DRM_AMDGPU'], 'm')
        self.assertEqual(values['CPU_SUP_AMD'], 'y')
        self.assertEqual(values['MODULE_SIG_PROTECT_LIST'], '""')
    def test_generated_make_config_quotes(self):
        self.assertEqual(auto_config('CONFIG_DRM=y\nCONFIG_CC_VERSION_TEXT="clang (build)"\n# CONFIG_AMD_IOMMU is not set\n'),
                         'CONFIG_DRM=y\nCONFIG_CC_VERSION_TEXT=clang (build)\n')
if __name__ == '__main__': unittest.main()
