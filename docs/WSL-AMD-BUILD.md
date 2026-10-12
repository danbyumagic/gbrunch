# Move the AMD build to Windows / WSL2

This sets up a development workspace. AMD Googlebook graphics are not ready for a laptop trial. The existing Intel boot path is separate. Do not install these kernel modules into WSL or write this package to a boot disk.

## 1. Install Ubuntu

In administrator PowerShell:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart if requested, then open Ubuntu and create its Linux username and password. Use roughly 150 GB available storage and preferably 16 GB host RAM. The Linux virtual disk grows as files are added.

## 2. Install build tools and clone the code

In Ubuntu:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates python3 python3-venv build-essential flex bison m4 bc libssl-dev libelf-dev pkg-config dwarves lz4 zstd xz-utils unzip cpio rsync qemu-system-x86 qemu-utils busybox-static meson ninja-build cmake
mkdir -p ~/build
cd ~/build
git clone https://github.com/danbyumagic/gbrunch.git
```

Keep source/build files under `~/build`, inside WSL's Linux filesystem. Avoid building under `/mnt/c`.

## 3. Download and extract the handoff package

Download `gbrunch-amd-build-handoff-20261012.tar.gz` using the supplied transfer link. It contains the experimental replacement kernel, matching modules, exact public ACK source archive, configs, build reports and module smoke results. It contains no Google recovery images or Google proprietary system/vendor binaries.

Copy it from Windows Downloads to `~/build` using File Explorer: enter `\\wsl.localhost\Ubuntu-24.04\home` in the address bar, open your Linux username, then `build`. Copy the accompanying `.sha256` file too.

In Ubuntu:

```bash
cd ~/build
sha256sum -c gbrunch-amd-build-handoff-20261012.tar.gz.sha256
tar -xzf gbrunch-amd-build-handoff-20261012.tar.gz
cd gbrunch-amd-build-handoff-20261012
python3 verify_package.py
```

The AMD kernel is under `kernel/arch/x86/boot/bzImage`, modules under `kernel/`, and reports under `reports/`. This is a build checkpoint, not a ready Googlebook disk image. Incremental kernel object files and the compiler are not included; a future rebuild uses the pinned source and compiler fetched by the repo scripts.

## 4. Resume with local Codex or this chat

Open `~/build/gbrunch` in your local Codex session (with WSL support), and give it `../gbrunch-amd-build-handoff-20261012/HANDOFF.md`. This chat does not automatically have terminal access to your PC. Alternatively run the supplied commands here and share their output.

The next work is Android AMD Mesa/minigbm/HAL integration, firmware selection from actual GPU IDs, and an isolated AMD boot image. Do not describe the passing QEMU kernel/module test as a successful Android or AMD graphics boot.

Google recovery can be downloaded directly from its pinned official source when needed. This is about 7.3 GB:

```bash
mkdir -p ~/build/gbrunch-private/downloads
cd ~/build/gbrunch-private/downloads
curl -fL --retry 3 https://dl.google.com/device/recovery/ruby-user/16452207/recovery.zip -o ruby-recovery.zip
echo '3c4dc7f636f29a1207e71d001fd2864aa20ce8354faecd2ef1ae47582b977f6c  ruby-recovery.zip' | sha256sum -c -
```

Never publish recovery-derived proprietary images or private device logs. The compiled AMD kernel has not been tested on physical AMD hardware.
