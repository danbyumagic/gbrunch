#!/usr/bin/env python3
"""Build a separate experimental AMD ACK kernel from a local recovery config.

Never edits a boot disk or the Intel profile. Requires a full, clean ACK source
checkout and Linux build tools. This produces kernel/module assets, not a ready
Android image: vendor/graphics integration and module-coverage checks remain gates.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
from build_amd_kernel_modules import config_values, verify_embedded_config

OVERRIDES = {
    'LOCALVERSION': '"-gbrunch-amd"', 'LOCALVERSION_AUTO':'n',
    'DRM_AMDGPU':'m', 'DRM_AMD_DC':'y', 'DRM_AMD_DC_FP':'y',
    'DRM_SIMPLEDRM':'y', 'SYSFB_SIMPLEFB':'y',
    'AMD_IOMMU':'y', 'AMD_PMC':'m', 'PINCTRL_AMD':'y',
    'X86_AMD_PLATFORM_DEVICE':'y', 'I2C_DESIGNWARE_CORE':'m',
    'I2C_DESIGNWARE_PLATFORM':'m', 'I2C_DESIGNWARE_AMDPSP':'y',
    'HWMON':'m', 'RUST':'n', 'ANDROID_BINDER_IPC':'y', 'ANDROID_BINDERFS':'y',
    'ANDROID_BINDER_DEVICES':'"binder,hwbinder,vndbinder"',
    'TRIM_UNUSED_KSYMS':'n', 'MODULE_SIG_PROTECT_LIST':'""',
    'MODULE_SIG_PROTECT':'n', 'DMABUF_HEAPS_SYSTEM':'y',
    'CRYPTO_HW':'y', 'CRYPTO_DEV_CCP':'y', 'CRYPTO_DEV_CCP_DD':'m', 'CRYPTO_DEV_SP_PSP':'y',
    'DEBUG_INFO_NONE':'y', 'DEBUG_INFO':'n', 'DEBUG_INFO_BTF':'n',
    'DEBUG_INFO_BTF_MODULES':'n', 'IKHEADERS':'n',
    'USB_XHCI_HCD':'y', 'USB_XHCI_PCI':'y', 'USB_STORAGE':'y', 'USB_UAS':'y',
    'SCSI':'y', 'HID_GENERIC':'y', 'USB_HID':'y', 'HID_MULTITOUCH':'y',
    'I2C_HID':'y', 'I2C_HID_ACPI':'y', 'KEYBOARD_ATKBD':'y', 'MOUSE_PS2':'y',
    'BLK_DEV_SD':'y', 'BLK_DEV_NVME':'y', 'NVME_CORE':'y',
    'BLK_DEV_DM':'y', 'DM_VERITY':'y', 'EXT4_FS':'y', 'EROFS_FS':'y',
}


def apply_options(config, overrides):
    values = config_values(config)
    values.update(overrides)
    return '\n'.join('# CONFIG_'+key+' is not set' if value=='n' else 'CONFIG_'+key+'='+value
                     for key,value in values.items())+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','kernel','config','clang','out'):
        p.add_argument('--'+name, required=True, type=pathlib.Path)
    p.add_argument('--jobs', type=int, choices=range(1,9), default=2)
    p.add_argument('--resume', action='store_true', help='Resume only an owned AMD build directory after fixing a build prerequisite')
    p.add_argument('--compile', action='store_true', help='Build bzImage and modules after configuration')
    p.add_argument('--host-sysroot', type=pathlib.Path)
    p.add_argument('--original-modules', type=pathlib.Path, nargs='+', help='Recovery module directories for coverage inventory')
    args=p.parse_args()
    source=args.source.resolve();out=args.out.resolve();clang=args.clang.resolve()
    if out.exists():
        marker=out/'gbrunch-build.json'
        if not args.resume or not marker.is_file() or json.loads(marker.read_text()).get('profile')!='separate-experimental-amd-kernel':
            raise ValueError('Choose a fresh output directory or explicitly resume an owned AMD build')
    if (source/'.config').exists() or (source/'include/config/auto.conf').exists():
        raise ValueError('Use a clean dedicated replacement-kernel source tree; preserve previous artifacts before cleaning')
    if not (source/'drivers/acpi/acpica/Makefile').exists():raise ValueError('Full kernel source tree required')
    minimum = 256*1024**2 if args.resume else 2*1024**3
    if shutil.disk_usage(out.parent).free < minimum:
        raise ValueError('Need at least 2 GiB free for a new build or 256 MiB for an owned incremental resume; full builds can require more')
    from amd_source_provenance import verify_source_manifest
    verify_source_manifest(source)
    config=args.config.read_text();kernel=args.kernel.read_bytes();verify_embedded_config(kernel,config)
    values=config_values(config);compiler=clang/'bin/clang-22'
    observed=subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0]
    if observed != values['CC_VERSION_TEXT'].strip('"'):raise ValueError('Recovery compiler mismatch')
    evidence=json.loads((pathlib.Path(__file__).resolve().parents[1]/'docs/amd/source-evidence.json').read_text())
    for path in ('drivers/gpu/drm/amd/amdgpu/Kconfig','drivers/gpu/drm/amd/display/Kconfig'):
        if hashlib.file_digest((source/path).open('rb'),'sha256').hexdigest()!=evidence['files'][path]['sha256']:
            raise ValueError('Source differs from the exact audited revision')
    out.mkdir(parents=True,exist_ok=args.resume);(out/'.config').write_text(apply_options(config,OVERRIDES))
    env=os.environ.copy();env['PATH']=str(clang/'bin')+':'+env['PATH']
    env['LD_LIBRARY_PATH']=str(clang/'lib')+':'+env.get('LD_LIBRARY_PATH','')
    hostflags=[]
    if args.host_sysroot:
        host=args.host_sysroot.resolve()
        env['PATH']=str(host/'usr/bin')+':'+env['PATH']
        env['M4']=str(host/'usr/bin/m4')
        env['BISON_PKGDATADIR']=str(host/'usr/share/bison')
        env['LD_LIBRARY_PATH']=str(host/'usr/lib/x86_64-linux-gnu')+':'+env['LD_LIBRARY_PATH']
        hostflags=['HOSTCFLAGS=-I'+str(host/'usr/include'),'HOSTLDFLAGS=-L'+str(host/'usr/lib/x86_64-linux-gnu')]
    command=['make','-C',str(source),'O='+str(out),'ARCH=x86_64','LLVM='+str(clang/'bin')+'/',
             'CC='+str(compiler),*hostflags,'-j'+str(args.jobs)]
    report={'source_commit':evidence['commit'],'compiler':observed,'profile':'separate-experimental-amd-kernel',
            'original_google_kernel_changed':False,'intel_profile_changed':False,'requested_options':OVERRIDES,
            'command':command, 'known_module_gaps':['Rust binder cannot be rebuilt in this C-only profile; C binder is built in'],
            'boot_tested':False,'android_tested':False,'hardware_tested':False}
    def save(): (out/'gbrunch-build.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'configure.log').open('wb') as log:
        result=subprocess.run(command+['olddefconfig'],env=env,stdout=log,stderr=subprocess.STDOUT)
    report['configure_exit_code']=result.returncode;save()
    if result.returncode:raise SystemExit(result.returncode)
    resolved=config_values((out/'.config').read_text())
    report['resolved_diff']={k:[values.get(k,'n'),resolved.get(k,'n')] for k in values.keys()|resolved.keys() if values.get(k,'n')!=resolved.get(k,'n')}
    report['requested_not_resolved']={k:resolved.get(k,'n') for k,v in OVERRIDES.items() if resolved.get(k,'n')!=v}
    # Compiler-derived/version/debug/Rust detail changes are explicitly reported.
    required={'DRM_AMDGPU':'m','DRM_AMD_DC':'y','DRM_AMD_DC_FP':'y','PINCTRL_AMD':'y',
              'X86_AMD_PLATFORM_DEVICE':'y','ANDROID_BINDER_IPC':'y','SYSFB_SIMPLEFB':'y'}
    if any(resolved.get(k,'n')!=v for k,v in required.items()):
        report['error']='Essential AMD/Android configuration did not resolve';save();raise SystemExit(2)
    save()
    if not args.compile:print(json.dumps({'configured':True,'report':str(out/'gbrunch-build.json'),'changes':len(report['resolved_diff'])}));return
    with (out/'compile.log').open('wb') as log:
        result=subprocess.run(command+['bzImage','modules'],env=env,stdout=log,stderr=subprocess.STDOUT)
    report['compile_exit_code']=result.returncode
    if result.returncode:save();raise SystemExit(result.returncode)
    compiled={m.name for m in out.rglob('*.ko')}
    original={m.name for directory in (args.original_modules or []) for m in directory.rglob('*.ko')}
    report['rebuilt_original_modules']=sorted(compiled&original)
    builtin_file=out/'modules.builtin'
    builtin={pathlib.PurePosixPath(line).name for line in builtin_file.read_text().splitlines()} if builtin_file.exists() else set()
    report['original_module_functionality_built_in']=sorted(original&builtin)
    report['original_module_files_not_rebuilt']=sorted(original-compiled)
    report['original_modules_without_matching_module_or_builtin']=sorted(original-compiled-builtin)
    report['module_coverage_complete']=bool(original) and not original-compiled-builtin
    image=out/'arch/x86/boot/bzImage'
    report['kernel_sha256']=hashlib.file_digest(image.open('rb'),'sha256').hexdigest()
    report['module_files']=sorted(compiled);save();print(json.dumps({'compiled':True,'report':str(out/'gbrunch-build.json'),'module_coverage_complete':report['module_coverage_complete']}))

if __name__=='__main__':main()
