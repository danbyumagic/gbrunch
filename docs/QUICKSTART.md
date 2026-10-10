# Experimental toolbox quick start

Use a dedicated USB drive or USB SSD of at least 64 GB marketed capacity. Writing the ISO erases its old installation. A 240 GB USB SSD is suitable with the patch below; the additional space is not automatically allocated to Android userdata.

## Download

The first public preview uses the previously QEMU-tested v0.2 ISO. Its SHA256 is:

```text
72a293967259183584ffdaf9249da5019ee13951024e4d1de1c1e7e0667f5ccc
```

Download it from [GitHub Releases](https://github.com/danbyumagic/gbrunch/releases/tag/v0.2-preview). Until that asset is available, the verified temporary mirror is:

```sh
curl -fsSL -c /tmp/gbrunch-cookies https://filebin.net/gbrunch-toolbox-v02-72a293967259 -o /dev/null
curl -fL --retry 3 -b /tmp/gbrunch-cookies https://filebin.net/gbrunch-toolbox-v02-72a293967259/gbrunch-toolbox-v0.2-amd64.iso -o gbrunch-toolbox-v0.2-amd64.iso
```

Mac checksum:

```sh
echo '72a293967259183584ffdaf9249da5019ee13951024e4d1de1c1e7e0667f5ccc  gbrunch-toolbox-v0.2-amd64.iso' | shasum -a 256 -c -
```

## Write it

On macOS, use `diskutil list external physical` and identify the dedicated external whole disk. Replace N with its current number; never copy someone else's disk number.

```sh
diskutil unmountDisk /dev/diskN
sudo dd if=./gbrunch-toolbox-v0.2-amd64.iso of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Ctrl+T shows macOS dd progress. Do not initialize the drive if macOS says it cannot read it.

On Linux, identify and unmount every mounted partition of the dedicated USB using `lsblk`. Write to the whole disk with `sudo dd if=gbrunch-toolbox-v0.2-amd64.iso of=/dev/REPLACE_WITH_USB bs=4M status=progress conv=fsync`. On Windows use a raw/DD writer, for example Rufus in DD mode. Choosing the wrong drive destroys its data.

## Larger-drive fix for the existing ISO

Boot the HP from the SSD/USB in UEFI mode with Secure Boot disabled, select normal Linux, open Terminal and type:

```sh
sudo sed -i 's/55\*G<=size<=70\*G/size>=55*G/' /opt/gbrunch/storage.py
```

Then select **Set up USB storage**, review the boot-drive identity and type its SETUP token. The patch only removes the upper capacity limit; minimum capacity, boot-USB identity, known ISO/GPT profile and write bounds remain checked. It does not resize existing Windows partitions. The initial Linux session is temporary, so apply the patch and run setup before rebooting. The ISO itself remains unchanged. New source builds include the corrected storage.py.

## Prepare Googlebook

1. After setup succeeds, reboot into normal Linux for persistence.
2. Connect to Wi-Fi or Ethernet.
3. Select **Prepare official recovery**; keep the terminal open. Logs are in GBWORK/logs/recovery-build.log.
4. Select **Prepare USB Googlebook trial**, review the drive and confirm TRY. Reboot when complete.
5. Select **Try Googlebook OS**. To troubleshoot, return to normal Linux and collect Android boot logs.

First validate the external trial. Internal installation is optional and requires manually prepared Windows unallocated space. See the main README and installer guides. The toolbox trial/internal Android layouts still require physical validation; QEMU copy/kernel-handoff tests are not a desktop guarantee.
