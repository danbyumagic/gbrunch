import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import launch


class LaunchGuards(unittest.TestCase):
    def test_host_devices_rejected(self):
        for path in ['/dev/null', r'\\.\PhysicalDrive0', r'\\?\GLOBALROOT\Device\Harddisk0']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                launch.regular(path)

    def test_manifest_hashes_and_missing_assets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            assets = {}
            for key in ('kernel', 'initrd', 'cmdline', 'disk'):
                content = b'console=ttyS0' if key == 'cmdline' else b'example'
                (root / key).write_bytes(content)
                assets[key] = {'file': key, 'sha256': hashlib.sha256(content).hexdigest()}
            manifest = root / 'vm.json'
            manifest.write_text(json.dumps({'profile_version': 1, 'assets': assets}))
            launch.assets_from_manifest(manifest)
            (root / 'kernel').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                launch.assets_from_manifest(manifest)

    def test_external_data_file_rejected(self):
        with mock.patch.object(launch.subprocess, 'run', return_value=mock.Mock(stdout=json.dumps({
            'format': 'qcow2', 'format-specific': {'data': {'data-file': '/dev/sda'}}}))):
            with self.assertRaisesRegex(ValueError, 'External QCOW2'):
                launch.image_info('qemu-img', 'disk')

    def test_disposable_command_has_no_devices_or_network(self):
        assets = {'disk': Path('base.qcow2'), 'kernel': Path('kernel'), 'initrd': Path('initrd')}
        command = launch.build_command(Path('qemu.exe'), assets, 'console=ttyS0', assets['disk'],
                                       'whpx', 4096, Path('serial.log'), False)
        self.assertEqual(command[command.index('-accel') + 1], 'whpx')
        self.assertIn('snapshot=on', command[command.index('-drive') + 1])
        self.assertEqual(command[command.index('-nic') + 1], 'none')
        self.assertFalse(any('PhysicalDrive' in arg for arg in command))
        persistent = launch.build_command(Path('qemu.exe'), assets, 'console=ttyS0', Path('userdata.qcow2'),
                                          'whpx', 4096, Path('serial.log'), False)
        self.assertNotIn('snapshot=on', persistent[persistent.index('-drive') + 1])


if __name__ == '__main__':
    unittest.main()
