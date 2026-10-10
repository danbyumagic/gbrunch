> Historical research/build log. Earlier statements describe that stage of development. See [README.md](README.md) for current status. Referenced private recovery files and raw device logs are intentionally not published.

# First HP external-drive test (prepare on macOS)

The prepared image boots a full hardware test batch. It collects your HP's exact device IDs, attempts matching Linux peripheral drivers, runs behavior checks, and automatically hands off to the original Googlebook kernel for its USB boot/logging test. It contains no Googlebook desktop. A working Googlebook desktop image still requires graphics and software-security integration.

BitLocker and Secure Boot are already disabled on your HP. Leave those settings as they are. You do not need to change the internal disk or install an operating system.

## Prepare the USB drive on your Mac

Download `build/gbrunch-hp-full-tests.img.gz`. The full-test download is about 130 MiB; the expanded image is 258 MiB. These commands assume the download is in `~/Downloads`.

Verify the compressed download and unpack it, retaining the gzip:

```sh
cd ~/Downloads
shasum -a 256 gbrunch-hp-full-tests.img.gz
gzip -dk gbrunch-hp-full-tests.img.gz
```

Expected compressed SHA256:

```text
7776bc214632d8c939478561c3eca8601f12a9ad5d6b92b8af180f658e216987
```

Connect the external drive and identify its whole-disk identifier:

```sh
diskutil list external physical
```

Below, replace **N** with the external drive's number. Check its model, capacity and external status first:

```sh
diskutil info /dev/diskN
```

**The next write erases the selected drive's partition layout. Use the external whole disk, not a partition such as `diskNs1`.** Unmount it (do not eject), then write through macOS's raw device:

```sh
diskutil unmountDisk /dev/diskN
sudo dd if=./gbrunch-hp-full-tests.img of=/dev/rdiskN bs=4m
sync
```

Press **Ctrl+T** while `dd` runs to display progress. Wait for it to finish successfully. macOS `dd` uses `bs=4m`; GNU's `status=progress` is unnecessary.

Verify the first 258 MiB by reading it back from the drive:

```sh
diskutil unmountDisk /dev/diskN
sudo dd if=/dev/rdiskN bs=1m count=258 | shasum -a 256
```

Expected read-back SHA256:

```text
190e7c35476f239a45d18a1c8cde2c14da202d29acd2f8b3f554af463196b622
```

If the hash matches, eject it:

```sh
diskutil eject /dev/diskN
```

If macOS offers to initialize the disk, choose **Ignore**. The FAT partition is named `GBRUNCH_HP`. The rest of a larger SSD is intentionally unused by this small diagnostic image.

The image writer targets the external drive you choose; the diagnostic environment itself mounts no internal HP filesystem. Do not use Disk Utility to reformat the flashed drive, rename its partition, or delete `GBRUNCH-MEDIA.TXT`.

## Boot the full batch once

1. Shut down the HP completely, connect AC power and the external drive, and turn it on while tapping **Esc**. Press **F9** for Boot Device Options and choose the external drive's **UEFI** entry. This selects it for this boot without changing the permanent boot order.
2. Leave the default **Full HP test batch, then Google kernel** selected. It starts after 12 seconds. It runs inventory, CPU checks and matching-driver tests. Allow several minutes. The screen may flicker when Intel graphics takes over.
3. When the input prompt appears, spend 40 seconds moving/clicking the touchpad, touching the touchscreen, pressing volume buttons and folding/rotating the laptop. Event counts and tablet switches are recorded; typed text is not stored. Sensor raw readings are sampled at the same time.
4. The speaker prompt offers **a** within 15 seconds to play a brief left/right check, if the SOF speaker card is identified. Note whether you hear both speakers. A muted or silent result is useful evidence; do not repeatedly reflash.
5. The suspend prompt offers **s** within 15 seconds. This optional test saves logs first, sets an RTC wake for 20 seconds, suspends, then collects resumed input activity for 10 seconds. If it does not wake after 60 seconds, try the power button; force shutdown if necessary. Missing wake support causes the test to refuse suspension. If you skip this test, the rest continues.
6. The batch saves its results, loads Google's original diagnostic kernel and attempts to start it automatically using `kexec`. Its screen may stop updating because Google disables the text framebuffer console. Wait at least 90 seconds. That second pass saves another log folder and powers off.
7. After shutdown, connect the drive to your Mac. Compress the whole `GBRUNCH_HP/GBRUNCH-LOGS` folder and send it back, along with your observations about screen behavior, speakers and suspend. Expect a `-linux` and a `-google` folder. The Linux folder's `test-summary.txt` identifies passed, failed, skipped and observational checks.

The camera briefly starts to check frame delivery; no photos, video or microphone recordings are retained. Wi-Fi scanning records frequency/signal evidence without storing SSIDs or access-point MAC addresses. It does not join a network or request credentials. Driver firmware loads into peripheral RAM; no firmware-flashing service runs.

## What is included

| Area | Tests/evidence in this image |
| --- | --- |
| CPU | Exact feature flags plus actual GFNI/VPCLMUL and AVX-VNNI instruction/digest checks when advertised |
| Graphics | Matching i915/MEI drivers and Intel firmware, connector modes/EDID, firmware errors, basic GPU no-op submission/completion on i915 |
| External USB/storage | USB topology/speed, marked-drive detection, persistent log writes, read-only 16 MiB read sample |
| Internal NVMe | Device IDs/read-only flags and read-only SMART health query; no internal filesystem mounts or storage writes |
| Wi-Fi | iwlwifi/iwlmvm plus firmware, radio-block state, interface and scan results |
| Bluetooth | Intel USB controller/firmware loading and binding/controller evidence |
| Audio | Meteor Lake SOF/codec/CS35L41 drivers and firmware, ALSA playback/capture enumeration, optional audible speaker check |
| Camera | UVC capabilities/current format and delivery of a few discarded frames |
| Input/tablet | I2C-HID, touchpad/touchscreen event counts, tablet/lid switch changes, HP/WMI binding |
| Sensors | ISH/HID/IIO driver loading, raw sensor samples during folding/rotation |
| Power | Battery/AC, supported sleep modes, wakeup sources and optional RTC-woken suspend/resume |
| USB4/Thunderbolt | Controller and connected-device topology, binding/errors; no authorization changes |
| Security | TPM driver binding/status evidence; no clearing, provisioning or credential operations |
| Googlebook kernel | Original kernel, USB/storage/input discovery, independent log collection and shutdown |

Bluetooth pairing, Wi-Fi association/internet, microphone recording, USB4 accessory transfers, GPU video playback and Android HAL/compositor/credentials cannot be fully validated by this batch. They require accessories, credentials, user observations or the unfinished Googlebook integration. The image includes the hardware evidence needed to plan those checks without another inventory-only flash. Linux driver success does not prove the corresponding Android HAL works.

## If something stalls

Inspect the logs before trying again. A saved initial Linux `COMPLETE.txt` confirms base collection, while `test-summary.txt`, `batch-tests.txt` and `kexec.txt` show later progress. `GBRUNCH_FULL_BATCH_COMPLETE` in `batch-tests.txt` confirms the extended batch finished. A missing Google folder means the handoff or original-kernel pass did not complete.

Use the same image's **Original Googlebook kernel** option if automatic handoff fails. It collects logs and powers off. If the full batch loses the display or stalls during extra driver loading, use **Basic inventory only** as the fallback. Photograph the last visible line and return any saved folders. These fallback options require no new image or reflash.

## Debugging and scope

Both options use maximum kernel verbosity, timestamps, an 8 MiB kernel log buffer and initcall tracing. Linux also provides a visible console. Logs are written only when exactly one drive matches the image's GPT identity, FAT serial and marker; other block devices are made read-only for this boot. A missing or duplicate marker causes log storage to be refused.

QEMU tests verify UEFI/USB3 boot, the extended batch, persistent logs, automatic Linux-to-Google-kernel transition and shutdown. An invalid marker test verifies refusal to write logs. These tests validate the boot image and logging path; they cannot establish your HP's physical USB, ACPI or peripheral behavior.

The Android experiment remains separate. It reaches verified system mounts and early Android userspace in QEMU, but graphics and software security still prevent a stable desktop. The first HP logs will establish the actual hardware before we select its compatibility drivers.
