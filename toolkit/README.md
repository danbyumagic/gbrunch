# GBRUNCH Toolbox v0.2

Debian 13 XFCE live desktop and local Googlebook builder, for a dedicated USB drive or USB SSD of 64 GB or larger. Write the hybrid ISO in raw/DD mode. Secure Boot must be disabled. The first session is temporary.

## Complete local workflow

1. Boot the USB and choose the normal Linux toolbox entry.
2. Select Set up USB storage, review the boot USB and confirm its token. Reboot into the normal entry to enable the persistent GBWORK workspace.
3. Connect Wi-Fi or Ethernet. Prepare official recovery downloads Google's pinned official Lenovo Ruby recovery, verifies its hash and builds a private local V7 compatibility view. Original download/extraction artifacts remain in GBWORK/recovery.
4. Select Prepare USB Googlebook trial. Review the identified boot USB and confirm the TRY token. This copies the verified view into unused space on that USB, checks each copy, creates fresh 16 GiB Android data and preserves the Linux toolbox/workspace.
5. Reboot and select Try Googlebook OS from the UEFI toolbox menu. Return to the normal Linux entry to collect Android logs, inspect hardware or use the browser/terminal.
6. Optionally select Install Googlebook on internal disk. Windows must already have one sufficiently large unallocated extent; this tool never shrinks NTFS. The reviewed INSTALL token authorizes copying into that extent with fresh 32 GiB data, a separate Googlebook ESP and Windows boot priority retained. Shut down and disconnect the USB after successful installation.

Trial boot is UEFI; legacy BIOS supports the Linux toolbox. The trial's EFI loader retains the original HP/QEMU hardware gate. Keep the working external V7 SSD separate as a fallback. Repeated trial overwrite and compatibility rollback are not implemented.

The local-image source is verified and exposed through read-only NBD. Trial copying happens before GPT commit; operation logs and original partition tables are saved in GBWORK/logs. Terminal transcripts are retained too. Diagnostics are local until you share them. Review reports for identifying information. GBWORK is ext4; Finder cannot ordinarily read it. Share from Linux or copy to another FAT/exFAT drive.

No Google-derived binary images are distributed in this ISO. Google system/super bytes are preserved; vendor compatibility is built locally. GNU/AOSP/firmware licenses and sources/manifests accompany the assets. Credits: skylartaylor/gbos-vm, sebanc/brunch, DangerousAndroid/AluminiumOS, Debian, Linux, Android Cuttlefish and linux-firmware.

Only the earlier external V7 Android build on one HP Envy is physically proven. Toolbox deployment/install integration uses QEMU dummy system/Windows data; no new physical trial/internal installation success is claimed. The live account is live/live with passwordless sudo. Android data is unencrypted for this experiment. AI assistance uses your own browser/terminal account; none is bundled. Debian versions are recorded, not yet pinned to a reproducible snapshot.

For drives larger than 64 GB, the existing v0.2 ISO needs the setup size-check fix in [the quick-start guide](../docs/QUICKSTART.md). New source builds include that fix.
