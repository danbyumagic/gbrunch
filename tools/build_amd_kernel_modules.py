#!/usr/bin/env python3
"""Recovery-local AMD Plan A preflight. Stops before forbidden config changes.

This is a preflight, not a completed module builder. Exit 2 means blocked.
Only public source metadata and local report files are written.
"""
import argparse
import base64
import hashlib
import json
import pathlib
import re
import urllib.request

SOURCE = 'https://android.googlesource.com/kernel/common'
OPTIONS = ('DRM_AMDGPU', 'DRM_AMD_DC', 'DRM_AMD_DC_FP',
           'DRM_SIMPLEDRM', 'AMD_PMC', 'PINCTRL_AMD',
           'X86_AMD_PLATFORM_DEVICE')


def config_values(text):
    values = dict(re.findall(r'^CONFIG_(\w+)=(.+)$', text, re.M))
    values.update({k: 'n' for k in re.findall(r'^# CONFIG_(\w+) is not set$', text, re.M)})
    return values


def forbidden_changes(before, after):
    """Strict Plan A: preserve every existing y and reject every new y."""
    return {k: [before.get(k, 'n'), after.get(k, 'n')]
            for k in before.keys() | after.keys()
            if before.get(k, 'n') != after.get(k, 'n') and
            'y' in (before.get(k, 'n'), after.get(k, 'n'))}


def source_file(commit, path):
    with urllib.request.urlopen(f'{SOURCE}/+/{commit}/{path}?format=TEXT', timeout=45) as r:
        return base64.b64decode(r.read()).decode()


def run(args):
    if args.out.exists():
        raise ValueError('Output exists; choose a fresh report directory')
    config = args.config.read_text()
    values = config_values(config)
    with args.kernel.open('rb') as f:
        data = f.read()
    versions = set(re.findall(rb'6\.18\.\d+-android17-\d+-g([0-9a-f]{12,40})-ab\d+', data))
    if len(versions) != 1:
        raise ValueError('Expected one exact Ruby Android17 kernel source revision')
    short = next(iter(versions)).decode()
    with urllib.request.urlopen(f'{SOURCE}/+/{short}?format=JSON', timeout=45) as r:
        metadata = json.loads(r.read().decode().split('\n', 1)[1])
    commit = metadata['commit']
    paths = ('drivers/gpu/drm/amd/amdgpu/Kconfig', 'drivers/gpu/drm/amd/display/Kconfig',
             'drivers/gpu/drm/sysfb/Kconfig', 'bazel/constants.scl')
    source = {p: source_file(commit, p) for p in paths}
    blocks = {}
    for text in source.values():
        for match in re.finditer(r'^config (\w+)\n(.*?)(?=^config |\Z)', text, re.M | re.S):
            blocks[match[1]] = match[2]
    blockers = []
    for option in OPTIONS:
        body = blocks.get(option)
        if body and re.search(r'^\s*(?:bool|def_bool)\b', body, re.M) and values.get(option, 'n') != 'y':
            blockers.append(f'CONFIG_{option} is boolean: required n -> y violates strict module-only rule')
    if values.get('SYSFB_SIMPLEFB', 'n') != 'y':
        blockers.append('SimpleDRM x86 UEFI fallback needs SYSFB_SIMPLEFB platform-device provisioning; disabled in recovery')
    clang = values.get('CC_VERSION_TEXT', '')
    constants = source['bazel/constants.scl']
    if 'r584948c' not in clang or 'r584948c' not in constants:
        blockers.append('Recovery compiler and source toolchain revision are not the expected matching r584948c')
    if values.get('MODULE_SIG_PROTECT') == 'y':
        blockers.append('Protected exports/module admission must be checked on the actual kernel; CRC equality alone is insufficient')
    report = {'status': 'blocked' if blockers else 'preflight-only', 'source_commit': commit,
              'source_url': f'{SOURCE}/+/{commit}', 'compiler': clang,
              'kernel_release': re.search(rb'6\.18\.\d+-android17-\d+-g[0-9a-f]{12,40}-ab\d+', data)[0].decode(),
              'kernel_sha256': hashlib.sha256(data).hexdigest(),
              'config_sha256': hashlib.sha256(config.encode()).hexdigest(),
              'requested_options': {k: values.get(k, 'n') for k in OPTIONS},
              'blockers': blockers, 'module_build_attempted': False,
              'abi_verified': False, 'firmware_packaged': False}
    args.out.mkdir(parents=True)
    (args.out/'preflight.json').write_text(json.dumps(report, indent=2)+'\n')
    for path, text in source.items():
        target = args.out/'public-source'/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    print(json.dumps(report, indent=2))
    return 2 if blockers else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=pathlib.Path, required=True, help='Locally extracted recovery kernel (uncompressed ELF or boot kernel)')
    p.add_argument('--config', type=pathlib.Path, required=True, help='Exact extract-ikconfig output for that recovery')
    p.add_argument('--out', type=pathlib.Path, required=True)
    args = p.parse_args()
    raise SystemExit(run(args))


if __name__ == '__main__':
    main()
