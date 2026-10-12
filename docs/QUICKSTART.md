# Experimental toolbox quick start

> **Experimental software: things can go wrong.** The system may fail to boot, crash or leave hardware unusable until you return to another OS. Disk-writing or installation mistakes can cause data loss. Back up important data, verify the target disk, and test externally before attempting internal installation.

Use a dedicated USB drive or USB SSD of at least 64 GB marketed capacity. Writing the ISO erases its old installation. A 240 GB USB SSD is suitable; the additional space is not automatically allocated to Android userdata.

## Download

The first public preview uses the v0.3 ISO. Its SHA256 is:

```text
818c5e37d9a2ba104cb700d0275055347a690bc1c9ab2a0e1e84286ba0955924
```

Download [Toolbox v0.3 ISO from MEGA](https://mega.nz/file/ni4hQR5b#mFKxoG_fPg1_PVpdaOECnvsIBhdFIavgJJb4lKcCs1I) and save it as `gbrunch-toolbox-v0.3-amd64.iso`. Verify the checksum below before writing it. The compatibility dependency archive is stored in this repository under `dist/`.

Mac checksum:

```sh
echo '818c5e37d9a2ba104cb700d0275055347a690bc1c9ab2a0e1e84286ba0955924  gbrunch-toolbox-v0.3-amd64.iso' | shasum -a 256 -c -
```

## Write it

On macOS, use `diskutil list external physical` and identify the dedicated external whole disk. Replace N with its current number; never copy someone else's disk number.

```sh
diskutil unmountDisk /dev/diskN
sudo dd if=./gbrunch-toolbox-v0.3-amd64.iso of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Ctrl+T shows macOS dd progress. Do not initialize the drive if macOS says it cannot read it.

On Linux, identify and unmount every mounted partition of the dedicated USB using `lsblk`. Write to the whole disk with `sudo dd if=gbrunch-toolbox-v0.3-amd64.iso of=/dev/REPLACE_WITH_USB bs=4M status=progress conv=fsync`. On Windows use a raw/DD writer, for example Rufus in DD mode. Choosing the wrong drive destroys its data.

## Boot and set up

Boot the HP from the SSD/USB in UEFI mode with Secure Boot disabled, select normal Linux, and choose **Set up USB storage**. Review the boot-drive identity and enter its SETUP token. This v0.3 ISO includes the larger-SSD fix; no manual patch is needed. Setup remains restricted to the dedicated toolbox boot USB/USB SSD.

## Prepare Googlebook

1. After setup succeeds, reboot into normal Linux for persistence.
2. Connect to Wi-Fi or Ethernet.
3. Select **Prepare official recovery**; keep the terminal open. Logs are in GBWORK/logs/recovery-build.log.
4. Select **Prepare USB Googlebook trial**, review the drive and confirm TRY. Reboot when complete.
5. Select **Try Googlebook OS**, then choose the tested HP/QEMU entry or **Experimental boot - untested hardware (verbose logs)**. To troubleshoot, return to normal Linux and collect Android boot logs.

First validate the external trial. Internal installation is optional and requires manually prepared Windows unallocated space. See the main README and installer guides. The toolbox trial/internal Android layouts still require physical validation; QEMU copy/kernel-handoff tests are not a desktop guarantee.
