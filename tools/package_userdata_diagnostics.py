#!/usr/bin/env python3
"""Package the open-source diagnostic VM; no Google image bytes included."""
import pathlib,shutil,json,hashlib,tarfile
R=pathlib.Path(__file__).resolve().parents[1];stage=R/'build/gbrunch-userdata-diagnostic-kit'
shutil.copytree(R/'build/userdata-maintenance-kit',stage,dirs_exist_ok=True)
for name in ['linux-kernel','initrd.gz','runtime-manifest.json']:shutil.copy2(R/'build/userdata-maintenance'/name,stage/name)
shutil.copy2(R/'tools/maintain_external_ssd_macos.py',stage/'maintain_external_ssd_macos.py')
for name in ['maintain_external_ssd_macos.py','maintain_userdata_guest.py','build_userdata_vm.py','prepare_native_android_gpu.py','test_userdata_overlay.py','test_userdata_macos_wrapper.py']:shutil.copy2(R/'tools'/name,stage/'source'/name)
hashes={name:hashlib.sha256((stage/name).read_bytes()).hexdigest() for name in ['linux-kernel','initrd.gz']}
(stage/'asset-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
for name in ['userdata-overlay-test.json','userdata-guard-tests.json']:shutil.copy2(R/'evidence'/name,stage/name)
(stage/'START-HERE-MAC.txt').write_text('''GBRUNCH journal-overlay diagnostic kit

This check does NOT write to the SSD. Only the selected external physical disk
is exposed, through file/raw QEMU nodes explicitly marked read-only. A temporary
local qcow2 overlay receives journal replay writes. No internal disk is exposed.
The temporary overlay is not a full SSD copy: only changed blocks occupy space.
Reports exclude the overlay and app data contents. No Android boot is required.

Extract in Downloads and run:

  cd ~/Downloads/gbrunch-userdata-diagnostic-kit
  diskutil list external physical

If GBRUNCH is still disk21, run:

  sudo "$(command -v python3)" maintain_external_ssd_macos.py \\
    --disk /dev/disk21 --action diagnose \\
    --qemu "$(command -v qemu-system-x86_64)" \\
    --qemu-img "$(command -v qemu-img)" \\
    --mcopy "$(command -v mcopy)" --mformat "$(command -v mformat)" \\
    --work "$HOME/Downloads/gbrunch-data-diagnose-2"

Wait for the report archive; a quiet terminal while the VM runs is normal.
Send ~/Downloads/gbrunch-data-diagnose-2-reports.zip, including if checks fail.
Keep the work directory and diagnostic overlay until the reports are reviewed.
Use a fresh work-directory name for every run. The tool refuses a preexisting one.

This collects original read-only fsck, quota/directory details, replays ONLY
committed journal transactions into the local overlay (e2fsck -E journal_only),
then records post-replay free space, fsck, quotas and directory listings. It does
not repair arbitrary filesystem damage or resize any partition in this mode.
Successful report collection is not a claim that the filesystem is healthy.

The guest overlay workflow was tested using a mounted ext4 fixture interrupted
by simulated power loss. Journal replay cleared needs_recovery, after-replay
fsck passed, and the original source userdata SHA256 stayed unchanged. The host
wrapper's disk identity and QEMU read-only block graph were tested separately;
macOS itself is unavailable in Work. Your previous readonly inspection already
verified the macOS raw disk/QEMU invocation on this Mac.

The existing expand action is experimental and still refuses the severe original
readonly fsck result seen on your SSD. Do not select it for this diagnostic run.
Original logging-v2 and all Google system/vendor/kernel bytes on the SSD remain
unchanged. This kit includes open-source tools, licenses and owned source only.
''')
archive=R/'build/gbrunch-userdata-diagnostic-kit.tar.gz'
with tarfile.open(archive,'w:gz') as tar:tar.add(stage,arcname=stage.name)
print(hashlib.sha256(archive.read_bytes()).hexdigest(),archive.stat().st_size)
