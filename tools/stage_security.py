#!/usr/bin/env python3
"""Stage x86 software security donors locally; does not graft or activate them.
The framework-side Trusty services/VINTF still require a compatibility-init design.
"""
import hashlib, json, pathlib, re, shutil, struct, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
CF = ROOT/'extracted/cuttlefish-x86'
OUT = ROOT/'build/compatibility-staging'
OUT.mkdir(parents=True, exist_ok=True)
sources = {
    'vendor/bin/hw/android.hardware.security.keymint-service.nonsecure':
        CF/'com.android.hardware.keymint.rust_nonsecure/payload/bin/hw/android.hardware.security.keymint-service.nonsecure',
    'vendor/lib64/gbrunch_keymint/libcrypto.so':
        CF/'com.android.hardware.keymint.rust_nonsecure/payload/lib64/libcrypto.so',
    'vendor/apex/com.android.hardware.gatekeeper.nonsecure.apex':
        CF/'vendor-files/apex/com.android.hardware.gatekeeper.nonsecure.apex',
}
files = []
for name, src in sources.items():
    dst = OUT/name; dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.is_symlink()
    shutil.copyfile(src, dst)
    b = src.read_bytes()
    item = {'path': name, 'source': str(src.relative_to(ROOT)),
            'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    if b.startswith(b'\x7fELF'):
        assert b[4] == 2 and struct.unpack_from('<H', b, 18)[0] == 62
        result = subprocess.check_output(['readelf', '-d', str(src)], text=True)
        item['elf_machine'] = 'x86_64'
        item['needed'] = re.findall(r'Shared library: \[(.*?)\]', result)
    files.append(item)
manifests = CF/'com.android.hardware.keymint.rust_nonsecure/payload/etc/vintf'
for src in manifests.glob('*.xml'):
    dst = OUT/'review-only-vintf'/src.name
    dst.parent.mkdir(exist_ok=True); shutil.copyfile(src, dst)
result = {'status': 'staged only, not a runnable vendor layer', 'donor_build': '16373615',
    'donor_target': 'aosp_cf_x86_64_only_phone-userdebug', 'files': files,
    'required_before_activation': [
        'Do not start stock protected or nonsecure Trusty VM, GSC startup/update or GSC daemon.',
        'Reconcile system_ext framework KeyMint/secureclock/sharedsecret declarations with donor device manifest.',
        'Select software Gatekeeper and remove stock Trusty Gatekeeper declaration/service.',
        'Deselect desktop StrongBox APEX; do not claim hardware-backed security.',
        'Resolve Weaver/Secretkeeper availability and framework compatibility matrix requirements.',
        'Validate x86 linker namespaces, private libcrypto loading and all dependency ABIs.',
        'Preserve SELinux labels/ownership; compile and validate enforcing policy for new service domains.',
        'Test fresh userdata key creation, credential enrollment, reboot/unlock and shared-secret protocol.',
    ]}
(OUT/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
