#!/usr/bin/env python3
"""Release open-source update tools + independent compatibility, no Google vendor."""
import pathlib,shutil,hashlib,json,tarfile
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/gbrunch-compat-v5-kit';O.mkdir(exist_ok=True)
for name in ['linux-kernel','initrd.gz','runtime-manifest.json']:shutil.copy2(R/'build/compat-update-v5'/name,O/name)
for name in ['update_external_ssd_v5_macos.py','maintain_external_ssd_macos.py']:shutil.copy2(R/'tools'/name,O/name)
shutil.copy2(R/'build/compat-graphics-v5/compat.ext4',O/'gbrunch-compat-v5.ext4')
shutil.copytree(R/'build/logging-v2-patch/licenses',O/'licenses',dirs_exist_ok=True)
shutil.copy2(R/'build/logging-v2-patch/SOURCES-AND-LICENSES.txt',O/'SOURCES-AND-LICENSES.txt')
src=O/'source';src.mkdir(exist_ok=True)
for name in ['compat_update_guest.py','native_vendor_in_vm.py','build_compat_update_v5_vm.py','inspect_recovery.py','maintain_userdata_guest.py','build_local_tool_vm.py','build_compat_probe.py','check_graphics_memfd_policy.c','extend_vendor_policy.c','graphics_client_domains.json','list_policy_attribute.c','android_persistlogs.sh','test_android_persistlogs.py','prepare_compat_runtime_view.py','test_compat_update_v5_vm.py','test_compat_update_v5_host.py','package_compat_update_v5.py']:shutil.copy2(R/'tools'/name,src/name)
shutil.copy2(R/'sources/gbos-vm/image/erofs_metadata.py',src/'erofs_metadata.py')
for name in ['compat-update-v5-vm-test.json','compat-update-v5-host-test.txt','compat-v5-final-runtime.json','graphics-v5-audit-before.txt','graphics-v5-audit-after.txt','logger-v3-failure-tests.json']:shutil.copy2(R/'evidence'/name,O/name)
original=R/'extracted/ruby/vendor_a-files/etc/selinux/precompiled_sepolicy'
(O/'request.json').write_text(json.dumps({'original_policy_sha256':hashlib.sha256(original.read_bytes()).hexdigest()},indent=2)+'\n')
assets=['linux-kernel','initrd.gz','gbrunch-compat-v5.ext4','request.json','update_external_ssd_v5_macos.py','maintain_external_ssd_macos.py']
(O/'asset-hashes.json').write_text(json.dumps({n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in assets},indent=2)+'\n')
(O/'START-HERE-MAC.txt').write_text("""GBRUNCH v5: application graphics audit + persistent diagnostics v3

V4 advanced past language and region selection. Google Play Services Quick Start
then hit allocator-memory permission failures. V5 audits all 43 appdomain members
of the pinned source policy, grants the four allocator memfd read/write/getattr/map
permissions to 41 application domains, excluding isolated_app and isolated_compute_app.
This includes regular untrusted apps; the old v3/v4 negative untrusted-app test is
intentionally superseded because regular apps need graphics. Isolated-app negative
checks remain. No executable-memory, arbitrary-file, MLS or permissive-mode changes.
This is a broader application-client fix, not merely another setup-screen workaround.

Logger v3 records ps -AZ, bounded CPU/top/pressure samples, dmesg, SurfaceFlinger
latency, per-app gfxinfo frame stats, and existing Android/service/display snapshots.
Its shell service receives CAP_SYSLOG and only read access to kernel syslog in the
local vendor policy, so kernel/SELinux errors can be captured. It also receives
read-only access to CPU/memory/I/O pressure files. Capture errors are
preserved. File size limits/timeouts remain. Package dumps reduced to first/last
snapshots; live logcat has 1MiB rotations (four files including active), reducing
log partition consumption. Snapshot capture stops at a 24MiB per-run budget
(or less when space is low), preserving room for live logs. If less than 8MiB
remains, a LOW_LOG_SPACE status is saved and capture stops. Old log directories
are not deleted. Logging remains
on GBLOG and independent of userdata; the original logging-v2 name is superseded.

This patch does NOT fix Bluetooth, promise smooth rendering, bypass setup/account
checks, or reset userdata. Source Google system, vendor, kernel, EFI and GPT remain
unchanged. Only GBRUNCH and derived GBVENDOR are written. Proprietary vendor bytes
are reconstructed locally from your SSD and must not be uploaded or redistributed.

Requires about 2GB Mac free space, existing Python/QEMU/mtools. Extract in Downloads:

  cd ~/Downloads/gbrunch-compat-v5-kit
  diskutil list external physical

If 240.1GB GBRUNCH SSD is still disk21 (not the 1TB disk6), run:

  sudo "$(command -v python3)" update_external_ssd_v5_macos.py \\
    --disk /dev/disk21 \\
    --qemu "$(command -v qemu-system-x86_64)" \\
    --mcopy "$(command -v mcopy)" --mformat "$(command -v mformat)" \\
    --work "$HOME/Downloads/gbrunch-compat-v5-update-1"

Use a NEW work directory. Wait for Completed update; keep local backups. The
source SSD is read-only during reconstruction. Device identity, GPT CRCs/GUIDs,
source profile, vendor bounds and policy checks are verified before host writes.
Both partitions are backed up, written and read-back verified; caught failures
attempt restoration when the same disk/GPT remain present. Do not unplug while
running. Send only gbrunch-compat-v5-update-1-reports.zip, not work.fat or backups.

After completion, diskutil eject /dev/disk21 and boot the same Android entry.
Test sequence: continue existing setup; note the last visible screen; if a button
opens a blank screen wait FIVE MINUTES without rebooting; then capture one log
archive. If setup completes, test desktop pointer responsiveness, open Settings,
and leave running five minutes. Do not reset userdata between these tests.

Once back on Mac, confirm actual disk/slice. If disk21s33 is 268.4MB GBLOG:

  cd ~/Downloads
  diskutil unmountDisk /dev/disk21
  sudo dd if=/dev/rdisk21s33 of=./gbrunch-v5-logs.fat bs=4m
  gzip ./gbrunch-v5-logs.fat

Upload gbrunch-v5-logs.fat.gz. Please note mouse vs touchscreen used, whether the
pointer is also choppy, last visible screen, and whether the display blanks or
returns to welcome. Physical graphics/performance and full desktop still need HP
validation; QEMU checks kernel/init/policy/logger only. Local updater read-only
source build, all 82 application security-context checks, independent-policy
comparison, partition fit, offset write/readback/rollback tests are bundled.
""")
archive=R/'build/gbrunch-compat-v5-kit.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(O,arcname=O.name)
print(archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())
