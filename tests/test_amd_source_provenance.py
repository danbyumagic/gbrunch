import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from amd_source_provenance import (  # noqa: E402
    SOURCE_ARCHIVE_SHA256,
    SOURCE_COMMIT,
    verify_source_manifest,
)


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.files = {}
        self.write_source('drivers/gpu/drm/amd/amdgpu/test.c', b'driver source\n')
        self.write_source('include/generated/test.h', b'generated header\n')
        self.write_source('arch/x86/include/generated/test.h', b'arch header\n')
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_source(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.files[name] = hashlib.sha256(content).hexdigest()

    def write_manifest(self, **overrides):
        data = {
            'source_commit': SOURCE_COMMIT,
            'source_archive_sha256': SOURCE_ARCHIVE_SHA256,
            'files': dict(self.files),
        }
        data.update(overrides)
        (self.root / 'gbrunch-source-files.json').write_text(json.dumps(data))

    def test_valid_manifest(self):
        self.assertEqual(verify_source_manifest(self.root), 3)

    def test_modified_driver_source_is_rejected_even_with_header_overlay(self):
        (self.root / 'drivers/gpu/drm/amd/amdgpu/test.c').write_text('modified')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_source_manifest(self.root, header_overlay=True)

    def test_wrong_commit_rejected(self):
        self.write_manifest(source_commit='0' * 40)
        with self.assertRaisesRegex(ValueError, 'commit'):
            verify_source_manifest(self.root)

    def test_wrong_archive_hash_rejected(self):
        self.write_manifest(source_archive_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'archive hash'):
            verify_source_manifest(self.root)

    def test_unsafe_paths_rejected(self):
        self.write_manifest(files={'../outside': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            verify_source_manifest(self.root)

    def test_header_overlay_skips_only_generated_header_trees(self):
        self.write_source('include/generated/test.h', b'changed header')
        self.write_source('arch/x86/include/generated/test.h', b'changed arch header')
        self.assertEqual(verify_source_manifest(self.root, header_overlay=True), 1)

    def test_symlink_source_is_rejected(self):
        target = self.root / 'drivers/gpu/drm/amd/amdgpu/test.c'
        target.unlink()
        target.symlink_to(self.root / 'include/generated/test.h')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            verify_source_manifest(self.root)


if __name__ == '__main__':
    unittest.main()
