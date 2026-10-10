#!/usr/bin/env python3
"""Release open-source update tools + independent compatibility, no Google vendor."""
import pathlib,shutil,hashlib,json,tarfile
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/gbrunch-compat-v6-kit';O.mkdir(exist_ok=True)
for name in ['linux-kernel','initrd.gz','runtime-manifest.json']:shutil.copy2(R/'build/compat-update-v6'/name,O/name)
for name in ['update_external_ssd_v6_macos.py','maintain_external_ssd_macos.py']:shutil.copy2(R/'tools'/name,O/name)
shutil.copy2(R/'build/compat-radio-v6/compat.ext4',O/'gbrunch-compat-v6.ext4')
shutil.copytree(R/'build/logging-v2-patch/licenses',O/'licenses',dirs_exist_ok=True)
shutil.copy2(R/'build/logging-v2-patch/SOURCES-AND-LICENSES.txt',O/'SOURCES-AND-LICENSES.txt')
src=O/'source';src.mkdir(exist_ok=True)
for name in ['compat_update_guest.py','native_vendor_in_vm.py','build_compat_update_v6_vm.py','inspect_recovery.py','maintain_userdata_guest.py','build_local_tool_vm.py','build_compat_probe.py','check_graphics_memfd_policy.c','extend_vendor_policy.c','graphics_client_domains.json','list_policy_attribute.c','android_persistlogs.sh','test_android_persistlogs.py','prepare_compat_runtime_view.py','download_hp_radio_firmware.py','check_policy_access.c','test_compat_update_v6_vm.py','test_compat_update_v6_host.py','package_compat_update_v6.py']:shutil.copy2(R/'tools'/name,src/name)
shutil.copy2(R/'sources/gbos-vm/image/erofs_metadata.py',src/'erofs_metadata.py')
for name in ['compat-update-v6-vm-test.json','compat-update-v6-host-test.txt','compat-v6-verified-runtime.json','graphics-v5-audit-before.txt','graphics-v5-audit-after.txt','logger-v4-failure-tests.json','compat-v6-boot-policy-checks.txt']:shutil.copy2(R/'evidence'/name,O/name)
original=R/'extracted/ruby/vendor_a-files/etc/selinux/precompiled_sepolicy'
(O/'request.json').write_text(json.dumps({'original_policy_sha256':hashlib.sha256(original.read_bytes()).hexdigest()},indent=2)+'\n')
assets=['linux-kernel','initrd.gz','gbrunch-compat-v6.ext4','request.json','update_external_ssd_v6_macos.py','maintain_external_ssd_macos.py']
(O/'asset-hashes.json').write_text(json.dumps({n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in assets},indent=2)+'\n')
(O/'START-HERE-MAC.txt').write_text("""GBRUNCH v6: HP radio firmware, SDR display, scaling, quieter diagnostics

Adds exact AX211 iwlwifi-ma-b0-gf-a0-89.ucode and Intel Bluetooth ibt-0180-0041.sfi
plus matching ddc, unmodified from linux-firmware commit
788aadc8f73d93908cf8545b2fc770fb6580a3f2 (20250509). Redistribution notices and
source/hash manifest are included. Firmware search path is /oem/firmware with
kernel normal fallback paths preserved. Original signed iwlmvm/backport modules
and dependencies are loaded during post-fs-data. No kernel/module bytes patched.
This addresses firmware failure; physical radio/HAL functionality needs HP testing.

Owned early-init overrides force_color_mode=7 (sRGB), persistent_hdr=false,
enable_color_pipeline=false, use_log_gamma_lut=false. qemu.sf.lcd_density=160
changes logical UI scale without changing the EDID-native 1920x1080 mode. These
are a conservative SDR experiment for the 6bpc AUO panel, not a proven haze fix.
A future comparison can restore original color properties in the compatibility
layer; original Google vendor build.prop is not modified.

DRM debug sysfs mask is set to0 after early-init, retaining initial boot logs and
kernel errors. Logger v4 retains initial ring once, bounded error/AVC/radio
extracts during snapshots and a final 1MiB ring tail. CPU/frame/process labels,
radio state, firmware path, effective HWC settings, density and Wifi dumpsys are
captured. Old 24MiB-or-free-space-minus8MiB capture budget remains. SELinux stays
enforcing. Init gets sysfs write and module-load permissions for original signed
modules; no module-loading permission is granted to application domains.

IMPORTANT: Existing GBLOG is backed up byte-for-byte as before-GBLOG.bin on your
Mac, then refreshed to create room for the next test. Only GBRUNCH, GBVENDOR and
GBLOG are written. GPT, userdata, EFI, Google original vendor/system/kernel are
not changed. This is not a userdata reset. Keep all local backups and do not
upload work.fat, vendor-local.erofs or backups; only small reports and collected
logs should be shared. Proprietary vendor reconstruction stays local.

Have about 3GB free on Mac. Existing Python/QEMU/mtools suffice. Extract in Downloads:

  cd ~/Downloads/gbrunch-compat-v6-kit
  diskutil list external physical

If 240.1GB GBRUNCH SSD remains disk21 (not 1TB disk6):

  sudo "$(command -v python3)" update_external_ssd_v6_macos.py \\
    --disk /dev/disk21 \\
    --qemu "$(command -v qemu-system-x86_64)" \\
    --mcopy "$(command -v mcopy)" --mformat "$(command -v mformat)" \\
    --work "$HOME/Downloads/gbrunch-compat-v6-update-1"

Use a NEW work directory. Wait for Completed update before ejecting. Reconstruction
reads SSD only; GPT/device/profile/partition checks precede writes. All three
partitions are backed up, synced, written and read-back hashed. Caught failures
restore all three when disk/GPT identity still matches. Interruptions can require
manual recovery; keep backups. Send gbrunch-compat-v6-update-1-reports.zip.

  diskutil eject /dev/disk21

HP test in one boot: check haze and UI size on home/Settings, pointer animation
and scrolling; check Wi-Fi and Bluetooth visibility, and connect Wi-Fi if possible.
Keep Ethernet available. Leave running five minutes after testing or any failure.
Do not reset userdata. Note what improved vs v5 and the last screen if it fails.

Back on Mac verify actual disk and 268.4MB GBLOG slice. If disk21s33:

  cd ~/Downloads
  diskutil unmountDisk /dev/disk21
  sudo dd if=/dev/rdisk21s33 of=./gbrunch-v6-logs.fat bs=4m
  gzip ./gbrunch-v6-logs.fat

Upload gbrunch-v6-logs.fat.gz. Original Google kernel/init/policy/logger are tested
under QEMU; QEMU cannot verify Intel panel colors, radio links or HP performance.
""")
shutil.copy2(R/'downloads/hp-radio-firmware/manifest.json',O/'radio-firmware-manifest.json')
for name in ['LICENCE.iwlwifi_firmware','LICENCE.ibt_firmware']:shutil.copy2(R/'downloads/hp-radio-firmware'/name,O/'licenses'/name)
archive=R/'build/gbrunch-compat-v6-kit.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(O,arcname=O.name)
print(archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())
