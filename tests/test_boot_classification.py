import importlib.util
import pathlib
import unittest


MODULE = pathlib.Path(__file__).resolve().parents[1] / 'vm/diagnostics/classify_boot.py'
SPEC = importlib.util.spec_from_file_location('classify_boot', MODULE)
classify_boot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(classify_boot)


class BootClassificationTests(unittest.TestCase):
    def test_explicit_milestones(self):
        result = classify_boot.classify(
            '[    0.000000][    T0] Linux version 6.18.21-test\n'
            '[    1.2] init: init first stage started!\n'
            '[    2.3] init: init second stage started!\n'
            'GBRUNCH_BOOT_COMPLETED=1\r\n')
        self.assertTrue(result['kernel_entry_observed'])
        self.assertTrue(result['first_stage_init_observed'])
        self.assertTrue(result['second_stage_init_observed'])
        self.assertTrue(result['boot_completed_observed'])
        self.assertFalse(result['graphical_boot_verified'])

    def test_observed_kernel_and_panic_formats(self):
        result = classify_boot.classify(
            '[    0.000000][    T0] Linux version 6.18.21-test\n'
            '[    2.875347][    T1] Kernel panic - not syncing: Attempted to kill init!\n'
            '[    2.869990][    T1] traps: init[1] trap invalid opcode ip:2e3160 sp:0 error:0 in init[x]\n')
        self.assertTrue(result['kernel_entry_observed'])
        self.assertTrue(result['kernel_panic_observed'])
        self.assertTrue(result['init_invalid_opcode_trap_observed'])

    def test_init_stage_phrase_inside_command_is_not_a_milestone(self):
        result = classify_boot.classify('echo init first stage started!\n')
        self.assertFalse(result['first_stage_init_observed'])

    def test_echo_command_is_not_boot_completion(self):
        result = classify_boot.classify('echo GBRUNCH_BOOT_COMPLETED=1\n')
        self.assertFalse(result['boot_completed_observed'])

    def test_property_name_without_diagnostic_marker_is_not_completion(self):
        for line in ('sys.boot_completed', 'sys.boot_completed=1',
                     'echo sys.boot_completed=1'):
            with self.subTest(line=line):
                self.assertFalse(classify_boot.classify(line)['boot_completed_observed'])

    def test_saved_properties_can_prove_runtime_but_not_graphics(self):
        result = classify_boot.classify('', '[sys.boot_completed]: [1]\n')
        self.assertTrue(result['boot_completed_observed'])
        self.assertFalse(result['graphical_boot_verified'])
        for value in ('[sys.boot_completed]: [0]', 'echo [sys.boot_completed]: [1]'):
            self.assertFalse(classify_boot.classify('', value)['boot_completed_observed'])

    def test_fatal_events_require_explicit_log_evidence(self):
        result = classify_boot.classify(
            '[    3.4] Kernel panic - not syncing: test\n'
            '[    4.5] traps: init[1][42]: trap invalid opcode ip 0x1\n'
            'F DEBUG : Fatal signal 11 (SIGSEGV)\n')
        self.assertTrue(result['kernel_panic_observed'])
        self.assertTrue(result['init_invalid_opcode_trap_observed'])
        self.assertTrue(result['userspace_fatal_signal_observed'])

    def test_process_names_or_exit_like_text_do_not_prove_boot(self):
        result = classify_boot.classify(
            'zygote started\nSurfaceFlinger running\nsys.boot_completed unset\nexit 0\ntimeout')
        self.assertFalse(result['kernel_entry_observed'])
        self.assertFalse(result['first_stage_init_observed'])
        self.assertFalse(result['second_stage_init_observed'])
        self.assertFalse(result['boot_completed_observed'])
        self.assertFalse(result['graphical_boot_verified'])


if __name__ == '__main__':
    unittest.main()
