#!/usr/bin/env python3
"""Package the open-source fresh-userdata maintenance VM, no Google bytes."""
import pathlib,shutil,json,hashlib,tarfile
R=pathlib.Path(__file__).resolve().parents[1];stage=R/'build/gbrunch-userdata-reset-kit'
shutil.copytree(R/'build/userdata-maintenance-kit',stage,dirs_exist_ok=True)
for name in ['linux-kernel','initrd.gz','runtime-manifest.json']:shutil.copy2(R/'build/userdata-maintenance'/name,stage/name)
shutil.copy2(R/'tools/maintain_external_ssd_macos.py',stage/'maintain_external_ssd_macos.py')
for name in ['maintain_external_ssd_macos.py','maintain_userdata_guest.py','build_userdata_vm.py','prepare_native_android_gpu.py','test_userdata_reset.py','test_userdata_macos_wrapper.py','test_userdata_overlay.py','package_userdata_reset.py']:shutil.copy2(R/'tools'/name,stage/'source'/name)
hashes={name:hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in ['linux-kernel','initrd.gz']}
(stage/'asset-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
for name in ['userdata-reset-test.json','userdata-guard-tests.json']:shutil.copy2(R/'evidence'/name,stage/name)
(stage/'START-HERE-MAC.txt').write_text('''GBRUNCH fresh 64GiB userdata kit

This mode switches Android to fresh userdata (apps/settings start over). It
formats a new 64GiB ext4 filesystem in unused SSD space. It retains the old
userdata bytes and existing Google system/vendor/boot/log partitions. The new
filesystem has original-compatible casefold, fsverity, user/group/project quotas,
4KiB blocks and 512-byte inodes. Its filesystem UUID is preserved. Android may
set its normal reserved-space allowance again on boot; ample free space remains.

Your approval to rebuild/reflash the experimental SSD also covers starting fresh
userdata. This targeted reset avoids downloading Google recovery again or copying
a 240GB disk onto the Mac. No proprietary system image is included or rewritten.
Only this selected SSD is exposed to the tool VM. It has no network or internal
Mac/HP disk access. The Mac needs several hundred MB for tool assets and reports.

Extract the archive in Downloads. Open Terminal:

  cd ~/Downloads/gbrunch-userdata-reset-kit
  diskutil list external physical

If the 240.1GB GBRUNCH SSD is still disk21 (NOT the 1TB disk6), run:

  sudo "$(command -v python3)" maintain_external_ssd_macos.py \\
    --disk /dev/disk21 --action reset \\
    --qemu "$(command -v qemu-system-x86_64)" \\
    --mcopy "$(command -v mcopy)" --mformat "$(command -v mformat)" \\
    --work "$HOME/Downloads/gbrunch-data-reset-3"

Use a NEW work-directory name if you have already attempted this run. Keep the
SSD connected until completion; a quiet terminal while QEMU runs is normal.
Expect several minutes. Do not reuse a failed work directory or bypass a refusal.

The wrapper checks the actual macOS WholeDisk/VirtualOrPhysical fields. The guest
validates GPT CRCs, userdata UUID/geometry and GBRUNCH/GBVENDOR/GBLOG UUIDs. GPT
backups are saved to the local work disk before writes. Only unused tail space
is formatted. Post-format readonly fsck must pass and size/UUID must match before
GPT is changed. All other partition records must remain identical. The backup
GPT is moved to the actual SSD end; the new primary and backup GPT are validated.
The old userdata region remains intact but is no longer selected by GPT.

When it prints Completed reset, send:

  ~/Downloads/gbrunch-data-reset-3-reports.zip

Then eject (if identifier is still disk21):

  diskutil eject /dev/disk21

Boot this external SSD on the HP using the same Android boot entry. Give first
boot several minutes. Existing logging-v2 remains enabled. A fresh filesystem
with space should remove the ENOSPC failure, but a completed desktop is unproven;
additional startup/HAL/security failures may appear once Android gets further.
Do not run reset a second time: the guest deliberately rejects relocated geometry.

If maintenance fails, send the report ZIP and preserve work.fat/GPT backups. Do
not boot assuming the reset succeeded. The original GPT is not changed unless all
format/check requirements pass. The old bytes permit later recovery; no automatic
rollback command is provided.

Validation: isolated VM reset created 64GiB, fsck clean, matching UUID/features;
original userdata SHA256 unchanged; every other partition record unchanged; QCOW
write map confined to new userdata plus primary/new-backup GPT; corrupt GPT,
wrong identity and insufficient space rejected. A failing formatter aborts before
GPT commit. Actual macOS reset is not tested in Work. The Mac raw-device interface
uses the same auto-detected protocol as your successful initial inspection; the
separate diagnostic protocol is corrected to host_device for macOS raw devices.
Source, licenses, package provenance and validation results are bundled.
''')
archive=R/'build/gbrunch-userdata-reset-kit.tar.gz'
with tarfile.open(archive,'w:gz') as tar:tar.add(stage,arcname=stage.name)
print(hashlib.sha256(archive.read_bytes()).hexdigest(),archive.stat().st_size)
