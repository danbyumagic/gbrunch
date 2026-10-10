# GBRUNCH standalone 32 GB USB installer

Private experimental build for the one tested HP Envy x360/Core Ultra 7 155U, board 8C4F. The external V7 desktop works on that laptop. Installing and booting Android from its internal NVMe is the next physical test; this kit does not claim support for other laptops.

This download contains Linux installer/build tools, our compatibility layer, Cuttlefish software security components and redistributable Intel firmware. It contains no Google recovery, kernel, module, system, vendor, policy or ramdisk bytes. Your Mac downloads the pinned official Lenovo/Ruby recovery from Google, verifies its ZIP and raw SHA256, and builds locally. Keep all generated recovery-derived files private. Original Google system and boot partitions remain unchanged; the local source view adds independent compatibility/vendor/log partitions and our boot files.

Use a spare marketed 32 GB USB. Preparation refuses physical USB drives outside 28–40 GiB, including the existing working 240 GB Googlebook SSD. The new USB is erased only after an explicit disk-specific confirmation. It receives a 128 MiB EFI partition, a 128 MiB FAT installer log partition and a 26 GiB ext4 payload partition. Its GPT backup matches actual physical capacity. The payload stores a sparse locally built disk image; the official ZIP is not copied onto the USB.

## Mac preparation

Install prerequisites as your normal user:

    brew install qemu mtools lz4

Extract the kit, then identify the NEW spare USB:

    diskutil list external physical

From the extracted kit directory, replace /dev/diskN with that USB's whole-disk identifier:

    sudo env PATH="$PATH" "$(command -v python3)" prepare_standalone_usb_macos.py \
      --disk /dev/diskN \
      --work "$HOME/Downloads/gbrunch-standalone-build"

Allow about 25 GiB free on the Mac for cached official downloads, sparse extraction and local build. --work may point to another mounted Mac drive. The actual sparse allocation depends on filesystem support. Preparation can take a while on Apple Silicon because Google's x86 build tools run in an emulated Linux VM. Build progress/errors are in assembly.log; USB preparation diagnostics are in prepare-vm.log and prepare-log.txt. Do not close the terminal mid-write. A failed run preserves reports and never reports success without filesystem checks and SHA256 readback. A completed cached source is hash-verified before reuse; incomplete builds need a new work directory. If you already have the exact official ZIP, add --recovery-zip /path/to/recovery.zip.

There is no Etcher step and no separate dd flash step. The helper passes ONLY the selected raw USB into the preparation VM and streams the local source into it. Other physical disks are not exposed to that VM. It prints the selected model, capacity and disk identifier before requesting ERASE /dev/diskN.

## Prepare Windows and install on the HP

Keep a current Windows backup. In Windows Disk Management, shrink C: by about 60000 MB, leaving that space UNALLOCATED. Do not create or format a new Windows volume there. The installer never shrinks Windows. This test assumes BitLocker decrypted, Secure Boot disabled, a 512-byte-sector standard GPT and an existing Windows EFI/unencrypted NTFS layout.

Disconnect the old working Googlebook SSD and connect only the new installer USB. Boot it through HP F9. Linux verifies the entire payload, mounts its filesystem read-only and exposes source.raw through a read-only loop device. The text interface shows disks and asks you to select the internal destination; inspection creates a partition plan before any installation writes. Only the existing unallocated region is eligible. After reviewing the exact plan, type its INSTALL confirmation.

The new installation uses fresh UUIDs, a separate Googlebook EFI partition, fresh 32 GiB Android data and a diagnostic log partition. Setup/accounts are fresh. Windows partitions and Windows EFI files are preserved, and Windows keeps first boot priority. After installation, disconnect the USB and choose GBRUNCH through F9. Keep the original external SSD as a fallback.

Do not run the previous external-SSD updater against the internal installation: it pins different UUIDs. Internal update/uninstall workflows and Google OTA behavior are not yet implemented or validated.

## Logs and limits

Installer plans, original GPT backup bytes, command logs, copy/readback status, EFI registration results, kernel diagnostics and payload verification are saved on the USB's GBINSTALL FAT volume. Copy that volume's files on the Mac. If FAT mounting is unavailable, collect just its 128 MiB image (replace N with the installer USB number):

    diskutil unmountDisk /dev/diskN
    sudo dd if=/dev/rdiskNs2 bs=4m count=32 | gzip > "$HOME/Downloads/gbrunch-installer-logs.fat.gz"

This collects installation logs, not subsequent Android runtime logs on the internal NVMe. Preserve logs and do not reinstall blindly if EFI registration or GPT commit fails. Caught commit failures restore and verify old GPT tables; sudden power loss between GPT writes is not atomic. Keep power attached.

Validation covers a full official recovery assembled locally, unchanged backing extents for every original non-EFI partition, exact V7 compatibility and working vendor-policy hashes, and QEMU preparation of a 32 GB USB. QEMU installation exercises actual Linux USB/read-only ext4/loop/NVMe devices, Windows-byte preservation, fresh 32 GiB formatting/fsck and firmware entry registration. Fixture system/Windows contents are dummy data, so those tests do not establish an internal Android boot on physical HP hardware. Bundled validation records describe their scope.

## Attribution and licensing

skylartaylor/gbos-vm: preserving official system partitions, vendor grafting and software security architecture; its MIT erofs_metadata.py is credited and included. sebanc/brunch: independent boot/compatibility-layer design. DangerousAndroid/AluminiumOS: research reference. Android Cuttlefish/AOSP provides open-source software KeyMint/Gatekeeper and boot components. Linux, Debian, GRUB, BusyBox, CPython, EROFS tools, e2fsprogs, mtools, util-linux, efibootmgr/efivar and Intel/linux-firmware supply the build/installer runtime.

Owned installer code uses the accompanying MIT license. Upstream software and firmware keep their own licenses/notices/source references. Googlebook OS is proprietary and is obtained only from Google's official infrastructure; it is not included in this kit. Source scripts/provenance are bundled; runtime rebuild scripts still expect the documented Work staging layout, whereas the shipped Mac preparation process is self-contained apart from Homebrew dependencies and the official download.
