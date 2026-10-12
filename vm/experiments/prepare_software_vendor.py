#!/usr/bin/env python3
"""Reproduce the local software graphics graft; not a full VM image installer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--vendor', required=True, type=Path, help='Existing locally built Ruby compatibility vendor EROFS')
p.add_argument('--donor', required=True, type=Path, help='Cuttlefish extraction with vendor-files/')
p.add_argument('--work', required=True, type=Path, help='New private working directory')
p.add_argument('--policy-tool', required=True, type=Path, help='Locally built tools/extend_vendor_policy.c executable')
for name in ('debugfs', 'dump-erofs', 'mkfs-erofs', 'fsck-erofs'):
    p.add_argument('--' + name, default=name.replace('-', '.'))
a = p.parse_args()
if a.work.exists(): p.error('Choose a new work directory')
if not a.vendor.is_file() or str(a.vendor.resolve()).startswith('/dev/'):
    p.error('Vendor must be a regular local file')
a.work.mkdir(parents=True)
a.work = a.work.resolve()
a.vendor = a.vendor.resolve()
profile = json.loads((Path(__file__).parent / 'software-profile.json').read_text())
expected = {x['component']: x['sha256'] for x in profile['graphics_components']}
files = []


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def donor_apex(name, members):
    apex = a.donor / 'vendor-files/apex' / name
    payload = a.work / (name + '.payload.img')
    with zipfile.ZipFile(apex) as archive, archive.open('apex_payload.img') as src, payload.open('wb') as out:
        while block := src.read(1024 * 1024): out.write(block)
    for target, inside in members.items():
        out = a.work / Path(target).name
        with out.open('wb') as stream:
            subprocess.run([a.debugfs, '-R', 'cat /' + inside, str(payload)], stdout=stream,
                           stderr=subprocess.PIPE, check=True)
        if digest(out) != expected[out.name]:
            raise RuntimeError(f'Donor component mismatch: {out.name}; use retained build 16373615')
        files.append({'path': target, 'source': str(out)})
    payload.unlink()


donor_apex('com.google.cf.vulkan.apex', {'lib64/hw/vulkan.pastel.so': 'lib64/hw/vulkan.pastel.so'})
files[-1]['metadata_from'] = 'lib64/hw/vulkan.intel.so'
libs = ['libminigbm_gralloc.so', 'libminigbm_gralloc4_utils.so',
        'android.hardware.graphics.allocator-V3-ndk.so', 'android.hardware.graphics.common-V7-ndk.so']
members = {'lib64/' + name: 'lib64/' + name for name in libs}
members['bin/hw/android.hardware.graphics.allocator-service.minigbm'] = 'bin/hw/android.hardware.graphics.allocator-service.minigbm'
donor_apex('com.google.cf.gralloc.apex', members)
donor_apex('com.android.hardware.graphics.composer.drm_hwcomposer.apex', {
    'bin/hw/android.hardware.composer.hwc3-service.drm': 'bin/hw/android.hardware.composer.hwc3-service.drm',
    'lib64/drm_hwcomposer_atom_reporter.so': 'lib64/drm_hwcomposer_atom_reporter.so'})
for name in ('mapper.minigbm.so', 'gralloc.default.so'):
    src = a.donor / 'vendor-files/lib64/hw' / name
    if not src.is_file(): raise RuntimeError(f'Missing donor file: {src}')
    files.append({'path': 'lib64/hw/' + name, 'source': str(src.resolve())})

props = subprocess.check_output([a.dump_erofs, '--path=/build.prop', '--cat', str(a.vendor)]).decode()
for key, value in profile['vendor_properties'].items():
    entries = props.splitlines()
    if not any(line.startswith(key + '=') for line in entries):
        raise RuntimeError(f'Expected vendor property is absent: {key}')
    props = '\n'.join(key + '=' + value if line.startswith(key + '=') else line for line in entries) + '\n'
prop_file = a.work / 'build.prop'; prop_file.write_text(props)
files.append({'path': 'build.prop', 'source': str(prop_file)})
old_policy = a.work / 'old-policy.bin'
old_policy.write_bytes(subprocess.check_output([a.dump_erofs, '--path=/etc/selinux/precompiled_sepolicy', '--cat', str(a.vendor)]))
new_policy = a.work / 'software-policy.bin'
subprocess.run([str(a.policy_tool.resolve()), str(old_policy), str(new_policy),
                'bootanim', 'bootanim', 'process', 'execmem'], check=True)
files.append({'path': 'etc/selinux/precompiled_sepolicy', 'source': str(new_policy)})
mapping = a.work / 'mapping.json'; mapping.write_text(json.dumps(files, indent=2) + '\n')
output = a.work / 'vendor-software.erofs'
subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'graft_vendor_files.py'),
                '--vendor', str(a.vendor), '--mapping', str(mapping), '--output', str(output),
                '--dump-erofs', a.dump_erofs, '--mkfs-erofs', a.mkfs_erofs, '--fsck-erofs', a.fsck_erofs], check=True)
manifest = {'input_vendor_sha256': digest(a.vendor), 'output_vendor_sha256': digest(output),
            'output_vendor_bytes': output.stat().st_size, 'original_inputs': 'unchanged',
            'status': 'graphics graft only; disk allocation and compatibility partition require separate assembly',
            'components': [{'path': item['path'], 'sha256': digest(Path(item['source']))} for item in files]}
(a.work / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Private local output:', output)
print('Use a matching kernel/module set and --with-system-heap --skip-shader-prewarm ramdisk sidecar.')
print('Rebuild the virtual vendor partition allocation if needed. Do not distribute this Google-derived output.')
