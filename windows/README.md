# Windows installation investigation

The current repository does not contain a working Windows-native installer for the single-partition design. See [the architecture and remaining gates](../docs/SINGLE-PARTITION.md).

`Test-InstallReadiness.ps1` is a **read-only report collector**, not an installer. It reports disks/partitions/free space, UEFI/Secure Boot, virtualization, BitLocker and existing WSL distributions. It does not install a Linux distribution, shrink/format a disk, change encryption, edit BCD/EFI or install Googlebook.

In Windows PowerShell, from this repository:

```powershell
.\windows\Test-InstallReadiness.ps1 -OutputDirectory "$env:USERPROFILE\Downloads\gbrunch-readiness-1"
```

If execution is blocked by Windows policy, do not change system-wide policy just for this preview. An administrator account may be needed for some inventory commands; denied checks remain unknown. The script has not been run on Windows in the cloud Linux environment. Inspect the generated JSON before sharing it.

A complete installer still needs: verified local image construction, an agreed filesystem/deployment engine, target-identity and encryption checks, crash recovery, EFI entry management, original-Windows preservation, a paired uninstaller and QEMU plus real HP validation. Having WSL available does not grant it access to the in-use Windows system disk.

The existing [Windows QEMU launcher](../vm/windows/README.md) is a separate VM experiment, not this installer.
