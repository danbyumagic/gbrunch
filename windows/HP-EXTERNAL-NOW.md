# Rebuild an HP external SSD from Windows

This is the temporary **traditional multi-partition** route for getting the HP Envy back to an external-drive trial. It bypasses the unfinished one-partition shutdown path. It does not repair that experiment or migrate an existing installation.

The build downloads the pinned official Lenovo Ruby R4 recovery from Google and combines it locally with the V7 HP compatibility assets, Google's original kernel and fresh 16 GiB Android userdata. The earlier recovery/V7 combination worked on the HP; **this R4 rebuild has not yet been physically tested**. Audio and the Googlebook Linux terminal remain unresolved. Google-derived results must stay private.

## Build

Use your existing Ubuntu x86-64 WSL installation; no new Linux distribution is installed. Ubuntu 24.04 or newer/Python 3.12+ is required by the asset unpacker. Allow at least 45 GB free for the sparse build/cache plus compressed output, and enough Windows disk space for WSL's disk to grow.

In the Ubuntu WSL terminal, install any missing build packages:

```sh
sudo apt update
sudo apt install -y python3 qemu-system-x86 qemu-utils mtools lz4 e2fsprogs gzip ca-certificates
```

Download the current experimental branch in Windows PowerShell:

```powershell
curl.exe -fL "https://github.com/danbyumagic/gbrunch/archive/refs/heads/experiment/single-partition.zip" -o "$HOME\Downloads\gbrunch-external.zip"
Expand-Archive "$HOME\Downloads\gbrunch-external.zip" -DestinationPath "$HOME\Downloads\gbrunch-external" -Force
$builder = Get-ChildItem "$HOME\Downloads\gbrunch-external" -Filter Build-HPExternal.ps1 -Recurse | Select-Object -First 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $builder.FullName
```

Alternatively, the GUI has **Build HP external OS...**, which opens the same builder in a separate console. No drive selection or NTFS preparation is needed to build an image. The build does not access a physical SSD.

The Google download is about 7.8 GB. Download, verification, assembly and compression can take tens of minutes depending on the connection and PC. In Ubuntu, check progress with:

```sh
tail -f ~/gbrunch-hp-external/build.log
```

After a successful build, open its directory from Ubuntu:

```sh
cd ~/gbrunch-hp-external
sha256sum -c gbrunch-hp-external-r4.img.gz.sha256
explorer.exe .
```

The file to flash is `gbrunch-hp-external-r4.img.gz`. A failed build is not a usable image. The script deliberately refuses an existing work directory; preserve its logs before choosing a new `GBRUNCH_EXTERNAL_WORK` path and retrying. Keep the QCOW2/cache backing files together.

## Flash and boot

**Flashing erases the entire selected external SSD, including every partition on it. Back up anything needed and verify the model/capacity. Do not select the HP's internal Windows disk.**

1. Open Rufus from its official site, <https://rufus.ie/>. Select the external SSD. USB SSDs may require enabling **List USB Hard Drives** in the advanced drive properties (Alt+F).
2. Choose the locally built `.img.gz` image and write it as a disk image/DD mode if prompted. Rufus supports gzip disk images. Do not use its normal Windows-ISO installation workflow. No preliminary NTFS format is required. Wait for completion.
3. Safely eject, connect the SSD to the HP, keep Secure Boot disabled, and use **Esc → F9 → external SSD UEFI**.
4. Choose **Googlebook OS – tested HP Envy / QEMU**. That label refers to the HP compatibility path; it does not mean this newer R4 recovery has been physically validated. Allow several minutes for first-boot app preparation.

If boot fails, retain the drive and collect its independent GBLOG rather than reformatting or repeatedly rebuilding. The image includes verbose kernel/init logging and the existing Android logger. This workflow does not change internal Windows partitions, BCD or the HP's permanent boot order. Rufus and the Windows/WSL interaction still need on-device testing; the cloud cannot write your SSD.

## Validation scope

The fresh-userdata step ran against the local R4 native assembly: GPT CRC checks, unchanged non-userdata partition entries, compatible ext4 features, read-only filesystem check, and QCOW2 integrity check passed. A file-only OVMF UEFI smoke test loaded GRUB, Google's original kernel and Android second-stage init without a kernel panic. No Intel GPU was available in that VM, so it does not prove a working HP desktop. The entire Windows build/export/Rufus sequence has not been run here. No Google image is distributed with the source.
