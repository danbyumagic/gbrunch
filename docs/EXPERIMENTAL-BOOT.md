# Experimental boot on another laptop

The v0.3 ISO and new source builds have two Android entries:

1. **Googlebook OS - tested HP Envy / QEMU**: default; retains the SMBIOS model/board gate.
2. **Experimental boot - untested hardware (verbose logs)**: explicitly attempts the same Intel-oriented build on another UEFI laptop.

The second entry changes only hardware admission. It uses the exact same kernel, matching modules, ramdisk, boot UUID and existing verbose logging settings. It does not select new drivers, bypass installer identity/partition checks or establish support for Dell/other machines. Early UEFI/kernel failures may occur before persistent Android logging starts.

Select **Try Googlebook OS** from the Linux toolbox's top-level UEFI menu first; these entries are in the next Android menu. Linux toolbox boot already has no HP model gate.

## Existing disks and the previously built ISO

The older v0.2 ISO, its bundled assembler and previously assembled disks predate this menu change. Pulling this repository does not modify an existing disk. A newly built ISO/local image uses the shared generator in tools/googlebook_boot_menu.py. Updated installers and asset packaging include that generator; original recovery bytes and system/vendor images are unaffected by this menu change.

To update an existing external trial/Googlebook disk without rebuilding Android, boot Linux and identify/mount **that disk's GBRUNCH Android EFI partition**. This is the Android ESP, not the toolbox ISO EFI or Windows ESP. Use `lsblk -f` to inspect labels; trial deployments use GBTRIAL_EFI. The target file must already be `EFI/GBRUNCH/grub.cfg` and contain the known GBRUNCH kernel/init configuration.

Download the standalone updater:

```sh
curl -fL https://raw.githubusercontent.com/danbyumagic/gbrunch/main/tools/googlebook_boot_menu.py -o googlebook_boot_menu.py
```

Replace the path below with the mounted Android ESP's actual configuration path:

```sh
sudo python3 googlebook_boot_menu.py --config /YOUR/MOUNT/EFI/GBRUNCH/grub.cfg
sync
```

The updater validates an unambiguous GBRUNCH command line, retains its arguments and saves the old configuration as `grub.cfg.before-experimental`. It changes only this owned text configuration. It refuses ambiguous/foreign configs and protects an existing backup. Running again on the already-upgraded menu makes no changes. To undo the menu change, restore the saved text file while the ESP is mounted and sync before rebooting.

There is no guarantee a different laptop will reach Android. Keep Secure Boot disabled for the current unsigned loader, use an external disk initially, record exact hardware IDs and collect the failure stage/logs. Do not treat an Intel CPU name as a complete hardware profile.

## Validation

Python tests check unchanged command-line extraction/UUID remapping, backup/idempotence and rejection of unsafe/ambiguous configs. GRUB's syntax checker validates the rendered menu. File-only QEMU tests exercise actual GRUB with simulated Dell and HP SMBIOS and the retained original Google kernel: Dell's guarded default is refused, while its explicit experimental entry reaches the original kernel; HP and QEMU defaults remain eligible. This is not a physical Dell test or an Android desktop test.
