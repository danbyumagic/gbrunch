# Write the same ISO on Linux or Windows

Use a spare 64 GB USB. The write erases that USB; preserve the working Googlebook SSD separately.

Download the ISO from https://filebin.net/gbrunch-toolbox-v02-72a293967259/gbrunch-toolbox-v0.2-amd64.iso

SHA256: 72a293967259183584ffdaf9249da5019ee13951024e4d1de1c1e7e0667f5ccc

Linux: verify with sha256sum. Use lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS to identify the whole 64 GB USB, unmount its mounted partitions, then write to that whole device:

```sh
sudo dd if=gbrunch-toolbox-v0.2-amd64.iso of=/dev/sdX bs=4M status=progress conv=fsync
```

Replace /dev/sdX with the verified whole USB device, never a partition or internal disk.

Windows: check the hash using PowerShell Get-FileHash -Algorithm SHA256, then use Rufus and select DD image mode when asked. File-extraction/ISO mode changes the partition layout and is not supported by this prototype's guarded workspace setup.

Boot on an x86_64 PC with Secure Boot disabled. On first launch, choose Set up USB storage, review its identification and confirmation token, then reboot into the normal entry. The workspace retains settings, diagnostics and locally downloaded recovery files. Use fallback without persistence if necessary. Prepare official recovery, prepare the USB Googlebook trial, reboot and select Try Googlebook OS in UEFI mode. Installation from the same local image is available after Windows has unallocated space; see START-HERE-MAC.md for the common Linux workflow.

For drives larger than 64 GB, the existing v0.2 ISO needs the setup size-check fix in [the quick-start guide](../docs/QUICKSTART.md). New source builds include that fix.
