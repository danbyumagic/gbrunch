# Single-partition boot investigation

The existing installer expands the recovery's GPT partitions onto the destination disk. This prototype investigates keeping those partitions inside one regular disk-image file instead. It does not migrate or change existing installations.

Current development uses [Ruby R4](recoveries/RUBY-R4.md), selected explicitly through its pinned recovery profile. The published v0.3 ISO remains on its original base.

**Update:** [full Android image-boot validation](ONE-PARTITION-VALIDATION.md) reached the welcome screen with persistent Android data in the software-rendered QEMU profile. The outer filesystem was not left clean after shutdown, so production boot and Windows installation remain gated. This is separate from the earlier dummy-file storage probe below.

## Proposed layout

```text
Existing Windows partitions and EFI System Partition
One added GBRUNCH partition
  googlebook.img
    Google's recovery partitions, independent compatibility/vendor partitions
    Android userdata and logs
  installation identity, manifest and update state
```

The existing EFI partition would also contain a dedicated GBRUNCH boot directory and entry. “One partition” means one additional data partition; it does not mean eliminating Windows' existing EFI/recovery partitions. Googlebook would still see its expected inner partitions.

An ext4 host filesystem is the initial prototype. Avoid image compression or QCOW2 in the boot path: Linux loop devices require a raw backing file. Preserve sparsity to avoid allocating all unused Android userdata up front, while reserving enough real space for growth.

## What is tested

`prototypes/image-container/probe.py` creates only new disposable regular files. A QEMU guest sees one outer GPT partition containing ext4 and `googlebook.img`; that image contains two dummy partitions. The guest mounts a system fixture read-only, writes a counter in the data fixture, unmounts cleanly, then repeats the boot. Both boots must pass and the counter must advance.

The initial run used Debian kernel 6.12.107 and passed two boots. The same probe then passed two boots with Google’s unchanged Ruby kernel (`7816c5d5…`), using its matching original virtio modules. Both also rejected a missing payload image. Readback verified the GPT checksums and unchanged dummy system partition bytes. This establishes the basic loop/GPT/filesystem mechanism, not Android first-stage mapping, Googlebook desktop, UEFI, power-loss behavior, performance or physical HP support. The older `tools/imageboot_*` experiments also describe NTFS/GRUB probes; their private historical outputs are not present in this restarted environment.

## Remaining boot work

- Original Google kernel and matching storage/filesystem/loop modules.
- Discover only the selected host filesystem by stable identity, rather than scanning/mounting arbitrary disks.
- Validate a manifest and complete inner GPT before permitting writes. Reject duplicate partition names/GUIDs and collisions with external recovery media.
- Expose inner `super`, boot/vbmeta, metadata, userdata and compatibility partitions to Android first-stage init. Merely creating `/dev/block/by-name` links does not prove fs_mgr will accept loop-backed dynamic partitions and AVB discovery.
- Keep the host filesystem and loop mapping alive through Android's switch-root, SELinux transition, device discovery and shutdown.
- Retain original system bytes/AVB data while restricting modifications to the private compatibility environment.
- Validate log persistence, low-space behavior, unclean shutdown and external-first hardware boot before migration.

## Installing from Windows

A Windows front end can download and verify Google's recovery and invoke the existing local build tools through an already installed WSL distribution. Building a file in WSL is not the same as safely installing it onto an internal disk.

A dedicated ext4 partition needs a Windows-native deployment step or a controlled first-boot helper. WSL cannot simply `--mount` the Windows system disk while it is in use. Do not base an installer on that assumption. A Windows-native writer could deploy a prepared ext4 filesystem image to a newly created, exclusively locked target partition; this needs explicit disk identity checks, revalidation, space checks, rollback and HP testing.

NTFS is another candidate: Windows can manage its files directly, but boot then needs a compatible NTFS driver and must refuse hibernated/unclean volumes. Never remove a hibernation file automatically. An image on C: has additional Windows Fast Startup and filesystem-recovery concerns; it is not the first proposed deployment format.

`windows/Test-InstallReadiness.ps1` currently collects read-only Windows/WSL/disk/BitLocker information. It is not an installer, was not executed on Windows here, and does not resize, format or change EFI/BCD. A missing/denied check means unknown, not safe.

The [Windows selector preview](../windows/README.md) now presents internal and USB drives, partitions and unallocated extents, with protected-partition and stale-target checks. It can save an exact proposed target but cannot install. This does not satisfy the full Android image-boot or Windows deployment gates above.

## Removal and updates

An eventual uninstaller must validate the installation UUID, remove only its own EFI directory/entry and single data partition, and leave Windows boot files untouched. Reclaiming that space into C: is possible only when the free extent is adjacent and Windows allows extension. One partition simplifies removal but does not guarantee one-click C: expansion on every disk layout.

Never delete the current scattered partitions on a user's behalf until a full backup, explicit identity check and validated migration/rollback workflow exist. The new layout does not automatically clean up old installations.
