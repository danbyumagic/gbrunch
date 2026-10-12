#!/usr/bin/env python3
"""Compile AMDGPU against recovery kheaders using the exact recovery compiler.

Stage one only: produces amdgpu.o, not an installable .ko. Missing export metadata
must never be bypassed by disabling MODVERSIONS or inventing symbol CRCs.
Use a dedicated local Android Common source tree; generated files are written there.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
import pathlib
import shutil
import subprocess
import tarfile
from build_amd_kernel_modules import config_values, verify_embedded_config


def extract_headers(module, destination, release):
    data = module.read_bytes()
    if ('vermagic='+release+' ').encode() not in data:
        raise ValueError('kheaders module does not match the recovery kernel release')
    start = data.find(b'\xfd7zXZ\x00')
    if start < 0:
        raise ValueError('No XZ kernel-header archive found')
    decoder = lzma.LZMADecompressor()
    raw = decoder.decompress(data[start:], max_length=128*1024**2)
    if not decoder.eof:
        raise ValueError('Kernel header archive exceeds size budget')
    count = 0
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            path = pathlib.PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe kernel header archive path')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Only regular kernel header files are supported')
            if not path.parts or path.parts[0] not in ('include', 'arch'):
                raise ValueError('Unexpected kernel header archive layout')
            target = destination/path
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Kernel header path escapes local source tree')
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(member).read()
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)
            count += 1
    return count


def auto_config(config):
    lines = []
    for line in config.splitlines():
        if not line.startswith('CONFIG_'):
            continue
        key, value = line.split('=', 1)
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        lines.append(key+'='+value)
    return '\n'.join(lines)+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'kernel', 'config', 'kheaders', 'clang', 'out'):
        p.add_argument('--'+name, required=True, type=pathlib.Path)
    p.add_argument('--host-cc', default='gcc')
    p.add_argument('--host-sysroot', type=pathlib.Path, help='Optional private host libelf/pkg-config sysroot')
    p.add_argument('--jobs', type=int, choices=range(1, 9), default=2)
    args = p.parse_args()
    source = args.source.resolve()
    from amd_source_provenance import verify_source_manifest
    verify_source_manifest(source, header_overlay=True)
    if args.out.exists():
        raise ValueError('Choose a fresh report output directory')
    # Pin source files before installing the recovery-derived headers.
    evidence = json.loads((pathlib.Path(__file__).resolve().parents[1]/'docs/amd/source-evidence.json').read_text())
    for relative in ('drivers/gpu/drm/amd/amdgpu/Kconfig', 'drivers/gpu/drm/amd/display/Kconfig', 'drivers/gpu/drm/amd/amdgpu/Makefile'):
        if hashlib.file_digest((source/relative).open('rb'), 'sha256').hexdigest() != evidence['files'][relative]['sha256']:
            raise ValueError('Source is not the audited recovery revision: '+relative)
    config = args.config.read_text()
    kernel = args.kernel.read_bytes()
    verify_embedded_config(kernel, config)
    values = config_values(config)
    expected = values['CC_VERSION_TEXT'].strip('"')
    compiler = args.clang.resolve()/'bin/clang-22'
    observed = subprocess.check_output([str(compiler), '--version'], text=True).splitlines()[0]
    if observed != expected:
        raise ValueError('Compiler build differs from the recovery compiler')
    import re
    release = re.search(rb'6\.18\.\d+-android17-\d+-g[0-9a-f]{12,40}-ab\d+', kernel)[0].decode()
    args.out.mkdir(parents=True)
    report = {'source_commit': evidence['commit'], 'kernel_release': release,
              'compiler': observed, 'stage': 'driver-object-compilation',
              'module_admission_verified': False, 'installable_module': False,
              'original_kernel_changed': False,
              'core_config_changed': False}
    report['headers_extracted'] = extract_headers(args.kheaders, source, release)
    (source/'.config').write_text(config)
    generated = source/'include/config'
    generated.mkdir(parents=True, exist_ok=True)
    (generated/'auto.conf').write_text(auto_config(config))
    (generated/'auto.conf.cmd').write_text('deps_config :=\ninclude/config/auto.conf: $(deps_config)\n')
    (generated/'kernel.release').write_text(release+'\n')
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(args.clang.resolve()/'lib') + ':' + env.get('LD_LIBRARY_PATH', '')
    if args.host_sysroot:
        env['PKG_CONFIG_SYSROOT_DIR'] = str(args.host_sysroot.resolve())
        env['PKG_CONFIG_LIBDIR'] = str(args.host_sysroot.resolve()/'usr/lib/x86_64-linux-gnu/pkgconfig')
    host_options = ['HOSTPKG_CONFIG=pkg-config']
    if args.host_sysroot:
        host_options += ['KBUILD_HOSTCFLAGS=-I'+str(args.host_sysroot.resolve()/'usr/include'),
                         'KBUILD_HOSTLDFLAGS=-L'+str(args.host_sysroot.resolve()/'usr/lib/x86_64-linux-gnu')]
    subprocess.run(['make', '-C', str(source/'tools/objtool'), 'HOSTCC='+args.host_cc,
                    'CC='+args.host_cc, *host_options, '-j'+str(args.jobs)], env=env, check=True)
    subprocess.run([args.host_cc, '-O2', '-I'+str(source/'scripts/include'),
                    str(source/'scripts/basic/fixdep.c'), '-o', str(source/'scripts/basic/fixdep')], check=True)
    command = ['make', '-C', str(source), 'ARCH=x86_64',
               'LLVM='+str(args.clang.resolve()/'bin')+'/', 'CC='+str(compiler),
               'M=drivers/gpu/drm/amd/amdgpu', 'CONFIG_DRM_AMDGPU=m',
               'CONFIG_DRM_AMD_DC=y', 'CONFIG_DRM_AMD_DC_FP=y',
               'KCFLAGS=-g0 -DCONFIG_DRM_AMDGPU_MODULE=1 -DCONFIG_DRM_AMD_DC=1 -DCONFIG_DRM_AMD_DC_FP=1',
               '-j'+str(args.jobs), 'amdgpu.o']
    report['command'] = command
    with (args.out/'compile.log').open('wb') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
    report['exit_code'] = result.returncode
    obj = source/'drivers/gpu/drm/amd/amdgpu/amdgpu.o'
    if result.returncode == 0 and obj.is_file():
        report['object_sha256'] = hashlib.file_digest(obj.open('rb'), 'sha256').hexdigest()
        report['object'] = str(obj)
    (args.out/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
