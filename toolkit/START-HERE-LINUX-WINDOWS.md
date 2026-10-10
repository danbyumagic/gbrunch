# Write the same ISO on Linux or Windows

> **Experimental software: things can go wrong.** The system may fail to boot, crash or leave hardware unusable until you return to another OS. Disk-writing or installation mistakes can cause data loss. Back up important data, verify the target disk, and test externally before attempting internal installation.

Use a dedicated USB drive or USB SSD of at least 64 GB. The write erases that USB; preserve the working Googlebook SSD separately.

Download the ISO from https://filebin.net/gbrunch-toolbox-v03-818c5e37d9a2/gbrunch-toolbox-v0.3-amd64.iso

SHA256: 818c5e37d9a2ba104cb700d0275055347a690bc1c9ab2a0e1e84286ba0955924

Linux: verify with sha256sum. Use lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS to identify the dedicated whole USB disk, unmount its mounted partitions, then write to that whole device:

```sh
sudo dd if=gbrunch-toolbox-v0.3-amd64.iso of=/dev/sdX bs=4M status=progress conv=fsync
```

Replace /dev/sdX with the verified whole USB device, never a partition or internal disk.

Windows: check the hash using PowerShell Get-FileHash -Algorithm SHA256, then use Rufus and select DD image mode when asked. File-extraction/ISO mode changes the partition layout and is not supported by this prototype's guarded workspace setup.

Boot on an x86_64 PC with Secure Boot disabled. On first launch, choose Set up USB storage, review its identification and confirmation token, then reboot into the normal entry. The workspace retains settings, diagnostics and locally downloaded recovery files. Use fallback without persistence if necessary. Prepare official recovery, prepare the USB Googlebook trial, reboot and select Try Googlebook OS in UEFI mode. Installation from the same local image is available after Windows has unallocated space; see START-HERE-MAC.md for the common Linux workflow.

This v0.3 ISO includes larger USB SSD setup and the explicit experimental Android boot entry for other laptops. No v0.2 manual patches are needed.
