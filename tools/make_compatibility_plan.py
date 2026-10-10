#!/usr/bin/env python3
"""Generate a hash-guarded review plan; no overlays/Google files are modified."""
import hashlib, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
base = ROOT/'extracted/ruby'
changes = {
    'system_a-files/system/etc/init/gscutil.rc': 'Mask post-fs GSC startup/firmware action before init parsing.',
    'system_a-files/system/etc/init/gscd.rc': 'Prevent GSC daemon startup; audit framework callers.',
    'system_a-files/system/etc/init/gscutil-executor.rc': 'Prevent GSC executor registration and privileged commands.',
    'system_a-files/system/etc/init/check_tpm_clear.rc': 'Prevent TPM-clear action on non-Google hardware.',
    'system_ext_a-files/etc/init/desktop-trusty_security_vm_launcher.rc': 'Suppress protected and nonprotected stock Trusty VM launch paths.',
    'system_ext_a-files/etc/init/android.hardware.security.keymint-service.desktop_trusty_system_vm.rc': 'Prevent stock VM KeyMint startup when selecting software donor.',
    'system_ext_a-files/etc/vintf/manifest.xml': 'Reconcile framework security HALs/accessors; preserve unrelated HIDL manager/token entries.',
    'vendor_a-files/etc/init/android.hardware.gatekeeper-service.trusty.rc': 'Replace Trusty Gatekeeper startup with nonsecure APEX selection.',
    'vendor_a-files/etc/vintf/manifest/android.hardware.gatekeeper-service.trusty.xml': 'Avoid duplicate Gatekeeper instance declaration.',
    'vendor_a-files/etc/init/fwupd.rc': 'Prevent boot-triggered fwupd and blocking firmware update.',
    'vendor_a-files/etc/init/android.hardware.boot-service.android-desktop.rc': 'Replace firmware-linked boot HAL with external-image slot implementation.',
    'vendor_a-files/etc/init/init.fatcat.rc': 'Review/replace board tuning, module selection and CPU power limits.',
    'vendor_a-files/etc/init/init.ruby.rc': 'Review/replace Ruby-specific power/display/audio policy.',
    'vendor_a-files/build.prop': 'Override ART ISA, hardware policy, StrongBox/Trusty selection in runtime vendor view.',
}
files = []
for name, action in changes.items():
    source = base/name
    assert source.is_file(), source
    files.append({'source': name, 'expected_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'review_action': action})
result = {'status': 'design/review plan, not applied or bootable',
    'official_build': 'ruby/16452207/CL3B.260622.271.R1',
    'original_image_sha256': '4f4490415d4db0721fa99ad10abd64b1b05c284b6c0e413907da948561de8c9e',
    'files': files,
    'unresolved': ['Weaver/Secretkeeper declarations and required framework matrix checks',
                  'SELinux policy assembly, labels and mount semantics',
                  'APEX factory-key/selection and linker namespace validation',
                  'Full inventory of privileged firmware executors and update entry points',
                  'Android first-stage compatibility-init implementation']}
out = ROOT/'build/compatibility-staging/compatibility-plan.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2)+'\n')
print('Recorded', len(files), 'hash-guarded review actions; no image modification.')
