# Windows installation investigation

The current repository does not contain a working Windows-native installer for the single-partition design. See [the architecture and remaining gates](../docs/SINGLE-PARTITION.md).

The [one-partition Android VM test](../docs/ONE-PARTITION-VALIDATION.md) now reaches the welcome screen and preserves Android data across boot. Clean outer-filesystem shutdown failed, and Windows deployment/EFI remain unverified. This does not enable the Install button.

## Drive and partition selector

`Open-Installer.cmd` opens the **experimental Windows preparation interface** using Windows PowerShell and the built-in WPF interface. It does not require another Linux installation or booting the toolbox ISO. Download this branch or clone the repository, open the `windows` folder and double-click `Open-Installer.cmd`. Alternatively:

```powershell
powershell.exe -NoProfile -STA -File .\windows\Start-Installer.ps1
```

This is experimental software. **The Prepare button really creates/formats a partition and erases its files.** Back up important data first. OS installation is still disabled: this version prepares temporary NTFS staging only. It does not write a Googlebook image, change EFI/BCD, or make a drive bootable. No recovery image is included or downloaded.

The selector:

- Lists internal drives and external USB SSDs by disk number, model, size, connection and partition scheme. USB SSDs need not report themselves as removable media.
- Shows individual partitions and sufficiently large unallocated extents. Nothing is selected by default. Free space inside C: is not unallocated disk space.
- Protects the current Windows volume, boot/system partitions, EFI, recovery, reserved, OEM and unknown partition types. Only non-system GPT basic-data partitions with confirmed decrypted status can be selected for replacement.
- Blocks offline/read-only disks, unknown health, missing stable identity, ambiguous connections and non-GPT disks. It does not convert MBR to GPT, shrink Windows, erase a whole disk or disable encryption.
- Describes erasure explicitly when selecting an existing data partition. Choosing an unallocated extent can create one data partition there.
- Refreshes inventory and checks disk identity plus target geometry again before saving the plan. Saving a plan never writes the target. Preparation requires its separate typed confirmation and new inventory checks.

### Format or prepare a partition

1. Open **Windows PowerShell as administrator** and launch `Start-Installer.ps1`. The Prepare button is disabled without administrator access.
2. Select the drive, then an eligible partition or unallocated extent. Read the drive model and target size carefully.
3. Click **Prepare staging (NTFS)...**. For an existing partition, type `ERASE DISK N PARTITION M` exactly as displayed. All files in that selected partition will be erased. For unallocated space, type the displayed `PREPARE DISK N` phrase. Closing the dialog cancels.
4. The selected partition is formatted NTFS and labelled `GBRUNCH_STAGE`. This is **temporary staging, not the final Googlebook filesystem**. The eventual ext4 deployment will replace this filesystem and its files again. There is no reason to prepare a working Googlebook SSD just to test the interface; doing so destroys its selected data partition.

The operation uses the entire selected extent, not the whole disk. It never automatically deletes partitions or creates an EFI partition. Journals go to `%LOCALAPPDATA%\GBRUNCH\Preparation\<operation-id>\preparation.json`. If preparation fails, inspect that journal and Disk Management before retrying: a newly created partition may remain. There is no automatic rollback of formatting or erased data. Windows Storage/formatting has not been tested on actual Windows hardware here.

A drive must have at least 64 GB nominal capacity. The proposed data partition needs at least 48 GiB; actual space requirements must be checked against the finished local payload before installation is enabled. The current preview uses the entire selected extent in its plan; partition sizing controls are future work. Existing Linux partitions are deliberately protected rather than guessed safe to replace. If BitLocker status cannot be established, replacement is blocked; an unallocated extent may still be selectable. Administrator access and the Windows BitLocker management commands may be needed for a complete inventory.

One data partition would contain `googlebook.img` and its internal Android partitions. EFI boot files are additional: an external boot drive needs its own EFI System Partition, while internal installation must validate the existing EFI partition and Windows boot preservation. **The preview does not yet choose or change an EFI partition.** No bootable installation is produced by saving a plan or preparing NTFS staging.

Inspect saved JSON before sharing it: it includes disk identities, partition labels and geometry. Windows PowerShell execution policy may block downloaded scripts; this launcher does not weaken system policy or automatically elevate privileges.

### Validation

```powershell
pwsh -NoProfile -File .\windows\Test-Preparation.ps1
```

The selection policy, stale-inventory checks, PowerShell syntax, WPF XML and mocked preparation operations were tested with PowerShell 7.4.13 on Linux (59 checks). Destructive commands in these tests are mocks: failures, mismatched identities and protected targets are checked without accessing a Windows disk. The real Windows Storage commands and WPF window have **not** been executed on Windows. This is separate from the successful R4 VM welcome-screen experiment, which still used the existing partition layout.

## Readiness report

`Test-InstallReadiness.ps1` is a **read-only report collector**, not an installer. It reports disks/partitions/free space, UEFI/Secure Boot, virtualization, BitLocker and existing WSL distributions. It does not install a Linux distribution, shrink/format a disk, change encryption, edit BCD/EFI or install Googlebook.

In Windows PowerShell, from this repository:

```powershell
.\windows\Test-InstallReadiness.ps1 -OutputDirectory "$env:USERPROFILE\Downloads\gbrunch-readiness-1"
```

If execution is blocked by Windows policy, do not change system-wide policy just for this preview. An administrator account may be needed for some inventory commands; denied checks remain unknown. The script has not been run on Windows in the cloud Linux environment. Inspect the generated JSON before sharing it.

A complete installer still needs: verified local image construction, an agreed filesystem/deployment engine, target-identity and encryption checks, crash recovery, EFI entry management, original-Windows preservation, a paired uninstaller and QEMU plus real HP validation. Having WSL available does not grant it access to the in-use Windows system disk.

The existing [Windows QEMU launcher](../vm/windows/README.md) is a separate VM experiment, not this installer.
