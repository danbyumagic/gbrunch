# GBRUNCH experimental Linux USB installer

Status: private development, for the HP Envy already running the tested V7 external SSD. Internal Googlebook boot is a new hardware test. This is not a general laptop installer.

## What it does

Boot a small redistributable Debian Linux environment from a spare USB. Connect the working Googlebook SSD as a read-only source. Inspect the internal Windows GPT, create an explicit installation plan, and copy into one pre-existing unallocated region only after the user types that plan's confirmation.

The installer does not shrink Windows. Shrink C: in Windows Disk Management first; about 60000 MB unallocated is suitable for the known source with fresh 32 GiB Android data. Keep a current Windows backup. BitLocker must be decrypted and Secure Boot disabled for this experiment. The current implementation requires a standard 512-byte-sector GPT with 128 entries, existing Windows EFI and unencrypted NTFS partitions, and an internal non-USB destination.

Google recovery partitions and the working independent vendor/compatibility layer are copied locally from the user's source SSD. No Google OS bytes are included in the USB download. Google system and kernel bytes are not edited. The copied EFI filesystem receives our own GRUB loader/configuration and a rewritten boot_a UUID. The destination gets fresh partition UUIDs, a separate Googlebook EFI partition, freshly formatted Android data, and an empty Android log volume. Existing external Android accounts/data are not migrated.

Existing Windows partition records and extents remain intact. Windows filesystems and its EFI files are never mounted or edited. A GBRUNCH firmware boot entry is appended after existing BootOrder entries. Windows remains first; choose GBRUNCH through the HP F9 menu. The source SSD remains a fallback.

## Failure handling and logs

Validate primary/backup GPT CRCs, disk identities, V7 compatibility hash, source kernel hash, free-space bounds and non-overlap before writing. Source reads use O_RDONLY and the source block disk is marked read-only. Writes are bounded to planned new extents; partition copies are SHA-256 verified by reading them back. Format userdata through an offset/size-limited loop device and run e2fsck. Commit GPT only after payload verification; caught errors during GPT commit restore the saved original tables and verify them.

These safeguards do not make sudden power loss atomic. A power failure between backup/primary GPT writes can leave inconsistent tables. Keep the USB's saved original GPT files and Windows backup; do not retry blindly after an interruption. The installer does not provide automatic uninstall or recovery for abrupt power loss, and does not certify Google OTA updates on this new layout.

The separate GBINSTALL USB FAT volume stores inspection plans, original primary/backup GPT bytes, per-command logs, copy progress/status, firmware boot listings, errors and installer kernel diagnostics. No proprietary system partition copies are placed on that log volume. Android runtime logs are written to the new internal GBLOG, as in the external installation.

If copying completed but firmware registration failed, preserve logs; do not reinstall. The new Googlebook EFI loader exists on its separate ESP, but firmware entry repair needs investigation.

## Validation scope

See bundled validation JSON and VM logs. Tests use dummy Windows/source disks in QEMU, actual Linux, ext4/mtools and GPT operations. They cover copy/readback, Windows byte preservation, UUID rewriting, overlap and identity guards, insufficient space, invalid GPT, injected copy failure and caught mid-GPT failure. The UEFI fixture uses a GNU Linux probe instead of Google's kernel/system; booting that fixture does not prove Android boots internally on the HP. Only the earlier V7 external installation is currently demonstrated on physical hardware.

## Rebuild

The builder is tools/build_installer_usb.py. Runtime/source provenance and upstream packages are recorded in runtime-manifest.json and dependency manifests. It uses the staged Debian kernel/module tree, GRUB, mtools, util-linux/efibootmgr, and the existing open-source Python/e2fs maintenance initramfs. Run the builder, prepare disposable fixtures, run test_installer_vm.py, then test_installer_uefi.py. Test files are under /tmp; no physical disk is accessed by these tests. The included scripts depend on the existing Work staging layout; this is not yet a standalone one-command source bootstrap.

## Attribution

skylartaylor/gbos-vm inspired preserving official system partitions while replacing hardware-specific vendor/security components. sebanc/brunch inspired the independent compatibility/boot layer. DangerousAndroid/AluminiumOS informed the original investigation. Android Cuttlefish supplies software KeyMint/Gatekeeper and related open-source components in the already-working locally built runtime. Debian, Linux, GRUB, BusyBox, CPython, e2fsprogs, mtools, util-linux, efibootmgr/efivar and glibc provide the installer environment. Upstream licenses and source locations accompany the download. Googlebook OS itself is proprietary and must be obtained from Google's official recovery infrastructure and assembled locally.

## HP storage evidence

The original Google kernel has CONFIG_NVME_CORE=y and CONFIG_BLK_DEV_NVME=y. The user's V6 Android startup logs already show the internal controller at PCI 0000:01:00.0, nvme0 queues initialized, and nvme0n1 with five existing partitions. This supports trying direct NVMe boot without replacing Google's kernel. CONFIG_VMD is absent in the Google kernel, so this is not evidence of support for other laptops whose NVMe is behind Intel VMD/RAID mode. Our Linux installer includes VMD support for inspection, but that does not add VMD support to Googlebook itself.

The current external-SSD updater is not an internal-install updater: it pins the external partition UUIDs. Internal partitions deliberately have new UUIDs. Do not run that updater against the internal disk. Internal update/uninstall workflows remain separate future work.

Final validation also exercises the production apply path on actual Linux USB/NVMe block devices inside QEMU: original downloaded Google kernel hash check, source BLKROSET/BLKROGET protection, full source byte preservation, existing dummy Windows byte preservation, 32 GiB userdata formatting/fsck, partition reread and the production efibootmgr registration code. The source contains dummy system partitions, so this is an installer test, not a Googlebook boot test. The kernel is read from the retained official recovery artifacts locally and is never bundled with this release.
