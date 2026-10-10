#!/usr/bin/env python3
"""Release open-source update tools + independent compatibility, no Google vendor."""
import pathlib,shutil,hashlib,json,tarfile
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/gbrunch-compat-v4-kit';O.mkdir(exist_ok=True)
for name in ['linux-kernel','initrd.gz','runtime-manifest.json']:shutil.copy2(R/'build/compat-update-v4'/name,O/name)
for name in ['update_external_ssd_v4_macos.py','maintain_external_ssd_macos.py']:shutil.copy2(R/'tools'/name,O/name)
shutil.copy2(R/'build/compat-weaver-v3/compat.ext4',O/'gbrunch-compat-v4.ext4')
shutil.copytree(R/'build/logging-v2-patch/licenses',O/'licenses',dirs_exist_ok=True)
shutil.copy2(R/'build/logging-v2-patch/SOURCES-AND-LICENSES.txt',O/'SOURCES-AND-LICENSES.txt')
src=O/'source';src.mkdir(exist_ok=True)
for name in ['compat_update_guest.py','native_vendor_in_vm.py','build_compat_update_v4_vm.py','inspect_recovery.py','maintain_userdata_guest.py','build_local_tool_vm.py','build_compat_probe.py','check_graphics_memfd_policy.c','extend_vendor_policy.c','test_compat_update_v4_vm.py','test_compat_update_v4_host.py','package_compat_update_v4.py']:shutil.copy2(R/'tools'/name,src/name)
shutil.copy2(R/'sources/gbos-vm/image/erofs_metadata.py',src/'erofs_metadata.py')
for name in ['compat-update-v4-vm-test.json','compat-update-v4-host-test.txt','compat-v3-runtime.json','hp-v3-settings-policy-before.txt','hp-v3-settings-policy-after.txt']:shutil.copy2(R/'evidence'/name,O/name)
original=R/'extracted/ruby/vendor_a-files/etc/selinux/precompiled_sepolicy'
(O/'request.json').write_text(json.dumps({'original_policy_sha256':hashlib.sha256(original.read_bytes()).hexdigest()},indent=2)+'\n')
assets=['linux-kernel','initrd.gz','gbrunch-compat-v4.ext4','request.json','update_external_ssd_v4_macos.py','maintain_external_ssd_macos.py']
(O/'asset-hashes.json').write_text(json.dumps({n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in assets},indent=2)+'\n')
(O/'START-HERE-MAC.txt').write_text('''GBRUNCH compatibility v4: Settings graphics metadata

V3 reached welcome/setup and stopped the captured system restart loop. After Next,
Settings language selection failed to allocate graphics buffers (-129 with Binder
EPERM). V4 adds the allocator memfd permission for system_app used by Settings.
This is a targeted candidate; physical HP behavior remains to be tested.

Changes: independent GBRUNCH overlays an empty Weaver VINTF fragment and excludes
its hardware-specific init rc. Independent GBVENDOR retains previous patches plus
read/write/getattr/map on allocator-owned memfd_file for platform_app, priv_app,
priv_app_36, and system_app. SELinux stays enforcing. No broad app-domain or permissive rule.
Launcher APK, Google system/system_ext/product/original vendor, kernel, EFI,
GPT, userdata and existing logs are not modified. No userdata reset or recovery
download is needed. Generated proprietary vendor bytes stay local on your Mac;
do not upload backups, work.fat, or vendor-local.erofs to Filebin.

Requires the same brew Python, QEMU and mtools already installed. Have about 2GB
free on the Mac for local vendor build and backups. Extract in Downloads, then:

  cd ~/Downloads/gbrunch-compat-v4-kit
  diskutil list external physical

If the 240.1GB GBRUNCH SSD is still disk21 (NOT your 1TB disk6), run:

  sudo "$(command -v python3)" update_external_ssd_v4_macos.py \\
    --disk /dev/disk21 \\
    --qemu "$(command -v qemu-system-x86_64)" \\
    --mcopy "$(command -v mcopy)" --mformat "$(command -v mformat)" \\
    --work "$HOME/Downloads/gbrunch-compat-v4-update-1"

Use a NEW work-directory name if repeating. Keep the SSD connected until the
script prints Completed update. A quiet terminal during VM build is normal;
expect several minutes. Source SSD is read-only during local reconstruction.
The guest validates GPT, pinned partition GUIDs and source vendor policy profile.
The host rechecks device identity and GPT before writes. Backups of GBRUNCH and
GBVENDOR are saved locally, both writes verified, and GPT remains byte-identical.
If a write/verification fails, the updater attempts to restore both local backups
when the same disk/GPT are still present. Keep the whole work directory until
successful HP testing; it contains recovery backups and private build files.
If interrupted, do not assume update or automatic restore finished; send reports.

After Completed update, send this small report ZIP (no vendor image/backups):

  ~/Downloads/gbrunch-compat-v4-update-1-reports.zip

Then eject and boot the same Android entry on the HP:

  diskutil eject /dev/disk21

Allow about five minutes and report whether setup/launcher stays up. Logging v2
remains active. If it still fails, collect the log partition as before, checking
its actual disk/slice identifier first. Do not reset userdata again for this patch.

Validation: original Google 6.18 kernel + Android init booted under UEFI/USB QEMU,
SELinux enforcing, new Weaver fragment bind-mounted and persistent FAT logs read
back. QEMU cannot verify Intel display or complete Googlebook desktop on the HP.
Offline policy checks include actual app MLS categories; targeted app buffers
allowed and unrelated untrusted_app still denied. Readonly-source vendor-builder
VM passed; output policy matches the independently patched candidate and fits existing partition.
Host updater tested real offset writes/readback on a disposable sparse fixture;
injected compatibility-write failure restored both backups, protected partition
markers and GPT stayed unchanged. The equivalent v3 updater completed verified writes on the Mac and booted HP
setup. The v4 permission was checked offline; v4 HP behavior remains untested. All open-source tool/compatibility bytes, source and notices
are bundled. Google proprietary vendor/boot/system/policy bytes are not bundled.
''')
archive=R/'build/gbrunch-compat-v4-kit.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(O,arcname=O.name)
print(archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())
