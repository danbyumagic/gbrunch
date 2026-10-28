# Build and flash the current HP external image on macOS

The current target is Lenovo Ruby **16658739 / R4**, Google's original kernel, the HP V7 compatibility environment and fresh 16 GiB Android data. This uses the **traditional multi-partition layout** to avoid the experimental one-partition shutdown issue. This R4 rebuild is not yet physically verified on the HP; the earlier recovery/V7 combination was. No Google-derived disk image is hosted for download.

## Build locally, then flash

Install the tools with Homebrew if needed:

```sh
brew install python qemu mtools lz4 e2fsprogs
```

Run without `sudo`:

```sh
curl -fL "https://raw.githubusercontent.com/danbyumagic/gbrunch/experiment/single-partition/macos/restore-hp-external.sh" -o "$HOME/Downloads/restore-hp-external.sh"
bash "$HOME/Downloads/restore-hp-external.sh"
```

The script downloads project source and the official Google recovery, builds privately under `~/gbrunch-hp-external`, and compresses the resulting disk image. It reuses an already completed compressed image/checksum there. Building needs about **45 GB free**, rather than a copy of the entire SSD. It uses QEMU for the isolated x86 build tools on both Intel and Apple Silicon Macs; it does not install another operating system on the Mac. Allow time for the roughly 7.8 GB recovery download, verification, assembly and compression.

The SSD is not touched during the build. Once it is complete, the script lists external physical disks and asks for a whole-disk path such as `/dev/disk21`. **Use the current disk number, not a number remembered from a previous connection.** It checks the model/capacity and requires `ERASE /dev/disk21` (with the actual selected identifier). This erases every existing partition/file on that external SSD. It refuses internal disks, partitions, virtual disks, smaller targets, the running macOS system disk and a target containing the input image.

The image is validated and streamed directly from gzip to the SSD. No uncompressed-image copy is required for flashing. The written bytes are read back and SHA256-checked before the drive is ejected. Do not disconnect it until verification finishes. If macOS offers to initialize the disk, choose **Ignore**.

Connect to the HP, leave Secure Boot disabled, and use **Esc → F9 → external SSD UEFI**. Choose the HP Googlebook entry and allow several minutes for first boot. This does not alter Windows or the permanent HP boot order. Preserve GBLOG and collect logs if it fails, instead of repeatedly reformatting.

## Flash an image already on the Mac

Download the standalone flasher and supply the locally built image plus its `.sha256` file:

```sh
curl -fL "https://raw.githubusercontent.com/danbyumagic/gbrunch/experiment/single-partition/macos/flash_external_ssd.py" -o "$HOME/Downloads/flash_external_ssd.py"
diskutil list external physical
python3 "$HOME/Downloads/flash_external_ssd.py" \
  --image "$HOME/Downloads/gbrunch-hp-external-r4.img.gz" --disk /dev/diskN
```

Replace `diskN` with the selected external whole disk. The checksum file must be named `gbrunch-hp-external-r4.img.gz.sha256` beside the image, or pass the local build checksum with `--sha256 HASH`. This checks integrity, not the identity of an arbitrary image publisher. Use your own local build. The flasher also accepts a raw `.img`; an official recovery by itself or a toolbox ISO is deliberately refused.

No Homebrew build tools are needed for this flash-only mode, just Python 3. Google-derived images stay private; do not upload them. If a build was interrupted, preserve its log; the builder refuses an existing incomplete work directory. Set `GBRUNCH_EXTERNAL_WORK` to a fresh path to retry without deleting artifacts. An interrupted flash is not a successful flash and must not be booted as though verification passed.

## Validation limits

Linux-host tests covered the GPT/checksum parser, corrupt-image refusal, internal/virtual/partition/read-only/small-target rejection, and APFS source-disk resolution with simulated plist records. Shell syntax was checked. The local R4 fresh-userdata build and original-kernel UEFI smoke test passed as described in [the Windows rebuild guide](../windows/HP-EXTERNAL-NOW.md). **Actual macOS `diskutil`/raw-device flashing and the entire Apple Silicon build have not been executed in the cloud.** The script uses the same isolated x86 assembly path, but on-device testing remains necessary.
