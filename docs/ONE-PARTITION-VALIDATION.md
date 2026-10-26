# One-partition Android boot: R4 experiment

**Googlebook R4 reached the visible welcome screen in QEMU with its complete raw disk image stored as a file inside one ext4 partition. Android data survived a second boot. Production shutdown did not pass.** The Windows installation button remains disabled.

[Sanitized machine-readable results](validation/one-partition-android-r4.json)

## What actually booted

The guest had one NVMe disk with one GPT data partition. Its 48 GiB ext4 filesystem contained a 37,367,071,232-byte `googlebook.img`, including the original recovery layout and separate local compatibility/vendor/data areas. The compatibility first stage attached that file to a loop device and retained the outer filesystem across the root switch.

This bypasses the stock first-stage assumption that boot partitions belong to a physical storage device. The wrapper creates the logical device mappings from the inner `super` partition, installs read-only dm-verity mappings using the signed recovery descriptors, mounts the separate compatibility vendor, then hands control to Google's original `/system/bin/init selinux_setup`. Google's system partitions were not edited. The original vbmeta embedded-key signature and boot hash descriptors were checked during preparation; this is not a new secure-boot trust anchor or rollback-protection implementation. Verity FEC correction was not enabled by the prototype.

The graphical trial used the existing Cuttlefish software-rendering profile and its matching 6.12 kernel/modules. A separate storage probe with Google's original 6.18 kernel mounted this real outer filesystem and discovered the complete nested recovery layout. **The graphical trial does not establish full Android image boot with Google's kernel on the HP.**

The cloud disk had less than 1 GB free. A host-side virtual storage adapter reused immutable recovery-backed data for the image file's extents, keeping writes in a private sparse file. This avoided another full recovery copy. Android saw an ordinary NVMe disk and used ext4/loop; it did not depend on NBD. The adapter and its backing chain are experimental test infrastructure, not a downloadable installation image. A standalone disk must contain the actual file data.

## Observed results

| Check | Result |
| --- | --- |
| Original Google kernel mounts real outer filesystem and discovers inner partitions | Passed |
| Compatibility first stage hands off to original Android second stage | Passed |
| Read-only dm-verity mappings created for all six original logical partitions | Passed |
| `sys.boot_completed=1` | Observed |
| Welcome screen with greeting, accessibility control and Next button | Visually verified |
| SELinux | Enforcing |
| Android userdata | Mounted read-write |
| Marker written in Android data, read after a second Android boot | Passed |
| GBLOG recovered after restarting | Passed |
| Wrong verity root in the owned compatibility initrd | Refused system mount before Android startup |
| Missing image filename | Refused loop attachment |
| Writes overlapping the original 12,884,901,888-byte `super` range | Zero private overlay blocks |
| Android-requested poweroff | Completed |
| Outer filesystem structure after poweroff, read-only e2fsck | No structural errors found |
| Outer filesystem marked clean after poweroff | **Failed** |

The negative tests changed only the compatibility initrd and used disposable virtual-disk snapshots. They did not alter Google's system images. The preservation check inspected every private overlay write against the protected source range; it was not a new full byte-stream hash.

## Remaining installation gates

The outer filesystem remained marked **not clean** even after Android-requested shutdown and sync. A structure check returning zero does not mean it was cleanly unmounted. Shutdown also logged a GBLOG unmount permission denial. The outer image and its loop/device-mapper users need an orderly shutdown protocol before installation is enabled; boot-time journal/recovery handling also needs validation. The prototype's `noload` mount must not become an unattended production recovery policy.

The first-stage prototype assumes the single attached test disk. A real boot must select a validated installation by stable identity, reject an unexpected image or layout, and avoid mounting arbitrary disks. The test loaded its kernel/initrd directly through QEMU, so EFI/GRUB integration is still unverified. External UEFI media normally also needs an EFI System Partition: “one partition” means one Googlebook **data** partition, with boot files in an appropriate EFI partition.

Other outstanding checks include the original Google kernel on HP, completed setup, networking, power-loss recovery, low-space behavior, and Windows deployment/uninstallation. The successful test used cached experimental userdata, rather than proving a clean first-install experience. No physical disk, Windows partition or HP boot configuration was changed.

Google recovery images, derived disk images, screenshots and raw guest logs remain private. Only this report and sanitized results are published. No new ISO or working Windows OS installer is released by this validation.
