# GBRUNCH Toolbox v0.2 — prepare and try Googlebook locally

Use a spare **64 GB or larger USB drive/USB SSD**. Writing the ISO erases that USB. Keep the working Googlebook SSD and 32 GB installer separate. Your Mac needs about 1 GB free for this ISO; the large recovery download/build happens on the USB in Linux.

```sh
cd ~/Downloads
URL=https://filebin.net/gbrunch-toolbox-v02-72a293967259
curl -fsSL -c /tmp/gbrunch-cookies "$URL" -o /dev/null
curl -fL --retry 3 -b /tmp/gbrunch-cookies "$URL/gbrunch-toolbox-v0.2-amd64.iso" -o gbrunch-toolbox-v0.2-amd64.iso
echo '72a293967259183584ffdaf9249da5019ee13951024e4d1de1c1e7e0667f5ccc  gbrunch-toolbox-v0.2-amd64.iso' | shasum -a 256 -c -
diskutil list external physical
```

Identify the **64 GB USB whole disk**. Replace N with its current number, not a partition suffix. Do not assume it is disk21 or use the 240 GB working SSD.

```sh
diskutil unmountDisk /dev/diskN
sudo dd if=./gbrunch-toolbox-v0.2-amd64.iso of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Ctrl+T prints dd progress on macOS. Ignore a “disk not readable” notification after writing; do not initialize it.

On the HP, keep Secure Boot disabled. Boot the USB in UEFI mode and choose the normal Linux toolbox entry. Select **Set up USB storage**, review its identity and type the SETUP token. Reboot into the normal Linux entry. Connect Wi-Fi from the network tray or use Ethernet.

Select **Prepare official recovery**. It downloads the official Lenovo Ruby recovery, verifies it, and assembles the local V7 image. The download is about 7.3 GB; Linux keeps the ZIP, sparse original raw recovery and compatibility view on GBWORK. The build uses an isolated Linux VM and can take several minutes. Do not fill the workspace with other files first. Build output is in GBWORK/recovery; logs are in GBWORK/logs/recovery-build.log.

Select **Prepare USB Googlebook trial**. It verifies the local image, displays the boot USB and requires a TRY token. It copies into the reserved USB tail and creates fresh 16 GiB Android data. Keep the drive connected and power attached until completion. Reboot and select **Try Googlebook OS**. The Linux toolbox remains the default boot entry and recovery path.

If the trial fails, reboot into Linux, select **Collect Android boot logs**, then **Open reports**. Upload the report ZIP through Firefox or copy it to another FAT/exFAT drive. Operation logs and console transcripts are retained under GBWORK/logs. Finder cannot ordinarily read GBWORK's ext4 filesystem. Reports stay local until you share them.

For optional internal dual boot: first boot Windows and use Disk Management to shrink C: by about 60 GB, leaving that space **unallocated**, without formatting it. Reboot the toolbox and choose **Install Googlebook on internal disk**. It uses the same verified local recovery view, shows the internal disk and partition plan, and requires its INSTALL token. Windows partitions/EFI files remain intact and Windows retains boot priority. The installer creates fresh 32 GiB Android data. After success, shut down, unplug the USB and choose GBRUNCH from the HP boot menu. If boot registration reports a problem, preserve its logs; do not blindly reinstall.

QEMU verified the deployment/installer with dummy system and Windows data, original Google kernel hash checks, and interrupted-GPT rollback. It does not establish physical HP trial/internal installation success. Only the earlier external V7 Android desktop is physically proven. The trial retains the HP/QEMU hardware gate. Android data is unencrypted for this experiment; this remains a private experimental USB.

For drives larger than 64 GB, the existing v0.2 ISO needs the setup size-check fix in [the quick-start guide](../docs/QUICKSTART.md). New source builds include that fix.
