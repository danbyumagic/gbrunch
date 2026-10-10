> Historical research/build log. Earlier statements describe that stage of development. See [README.md](README.md) for current status. Referenced private recovery files and raw device logs are intentionally not published.

# Local reproduction

This workspace contains a research build, a tested kernel/UEFI probe, and staged software-security donors. It does **not** contain a working Googlebook desktop image or an HP installer. Do not redistribute locally downloaded Google images or images containing their payloads.

The source and evidence paths are relative to `/workspace/gbrunch`. Scripts derive that root from their own location. A Linux x86-64 host with Python3, `curl`, `dpkg-deb`, `bash`, `readelf`, GNU file utilities, and sufficient space is required. No root, mounts, physical block-device writes or laptop access are needed. The locally restored Debian trixie binaries require a compatible host glibc for inspection/GRUB; the QEMU sysroot supplies its pinned libraries. This environment satisfies those requirements. A fresh workspace should budget at least 35–40 GB, preferably more for additional images/build sources; sparse files materially reduce current usage.

## Restore tools

```sh
cd /workspace/gbrunch
python3 tools/bootstrap_tools.py
```

This restores exact package files from `tools/debs/selected.json` and the tool evidence manifests, checks SHA-256, and extracts them into `tools/local` and `tools/qemu`. It never executes Debian maintainer scripts or installs host packages. If an exact version disappears from the Debian mirror, fetch the same package from Debian's snapshot infrastructure and verify the recorded SHA-256; do not silently substitute a new version.

The upstream Python AVB tool and Linux extraction scripts are already retained in `tools/`. Source checkouts and their commits are recorded in `evidence/source-commits.json`. Reproduction is currently from these retained source/evidence files; this is a first research scaffold, not a packaged release/bootstrap from an empty directory.

## Official recovery preparation and forensic checks

```sh
python3 tools/prepare_recovery.py --download --inspect
python3 tools/verify_avb.py --slot b
```

`--download` fetches only the pinned Google HTTPS URL when missing, verifies the complete ZIP SHA-256, extracts the official member as a sparse file, and verifies its SHA-256 and length. Existing downloads are verified again. `--inspect` reads both boot slots, parses GPT/liblp, extracts the active system/vendor/module filesystems, extracts kernel/config, inventories modules and verifies slot A AVB trees/hashes. No original image is opened writable. Repeated full hashing/tree verification takes time.

The raw file remains `downloads/ruby-recovery.raw`; `downloads/ruby-recovery.zip` is also retained. Do not turn these into device-install targets. The official production catalog snapshot, all recovery HEAD results and download/hash records are in `evidence/`.

## Software-security donor preparation

```sh
python3 tools/prepare_cuttlefish.py
python3 tools/make_compatibility_plan.py
```

This fetches the pinned official Android CI x86 build when missing, verifies the recorded SHA-256, extracts its sparse super container, reads the vendor extents without materializing the whole disk, and extracts software KeyMint/Gatekeeper and boot HAL APEX payloads. Nonsecure donor binaries/APEX and a private crypto library are staged in `build/compatibility-staging`.

The staged files are **not activated or grafted**. `build/compatibility-staging/manifest.json` records ELF architecture, dependencies and hashes plus the remaining init/VINTF/SELinux/credential gates. `compatibility-plan.json` records 14 build-specific, hash-guarded service/property/manifest review actions; it does not apply them. Never replace the system's global libcrypto with the donor library. Remote Cuttlefish security variants are not the chosen donors.

## Build and test the boot probe

```sh
python3 tools/build_boot_probe.py
python3 tools/test_boot_probe.py
```

Output: `build/boot-probe/gbrunch-boot-probe.img`, 136,314,880 bytes (130 MiB), GPT + FAT32 EFI System Partition. The standalone GRUB EFI loader embeds the untouched official kernel and a generated BusyBox initramfs. The probe loads Google's original signed virtio transport/block modules, prints PCI IDs/subsystem IDs/driver bindings and ACPI IDs, lists kernel-visible block devices, and powers off. It mounts only proc/sysfs/tmpfs, with no block filesystem mounts and no Android/firmware service startup.

The QEMU test uses OVMF, q35, TCG, a serial console, read-only NVMe and virtio attachments of the disk file, no network and no passthrough. Only the disposable OVMF variable file is writable. It asserts kernel/init completion, signed module load, virtio device enumeration and clean process exit. Evidence:

* `evidence/boot-probe-test.json`: test command and assertions.
* `evidence/boot-probe-uefi.log`: actual kernel/probe output.
* `build/boot-probe/manifest.json`: output hash, original-kernel hash and allowlisted command line.

There is no graphical Linux console in this stock kernel (VT/simpledrm disabled). The probe is useful for VM boot development, but **is not yet an interactive HP diagnostic image**. Secure Boot was not enabled or tested; the current experimental loader is unsigned. No firmware-setting changes were made.

## Current limits and the next implementation

The boot probe establishes EFI → original kernel → custom initramfs, plus original module loading. It does not mount Android partitions, launch Google init/system_server, graft vendor, integrate software security or test physical Meteor Lake graphics/audio. Later VM-only Android experiments are documented below; the standalone EFI probe itself retains this limited scope.

The next source component should be a matching Android17 first-stage compatibility init, with liblp/fs_mgr/AVB mounts, strict boot-medium identification, early immutable vendor/system-service view composition, appropriate SELinux setup and handoff to Google's original second-stage init. That component must be implemented and tested before generating a full Googlebook external-disk file. Do not run the recovery-media slot as a shortcut to normal boot.

The process is version-pinned and reviewable; byte-identical FAT/GRUB output is not yet guaranteed because timestamps are not fully normalized. The generated manifest provides the actual hash for every build. The original recovery and donor hashes remain fixed.


## Run the actual Android userspace probes

Stock TCG cannot execute several instructions used unconditionally by Ruby’s Panther Lake userspace. The local experimental QEMU patch adds the GFNI, 256-bit VPCLMULQDQ and AVX-VNNI forms encountered in boot. Build dependencies are restored into owned directories, without a system installation:

```sh
python3 tools/prepare_qemu_build.py
bash tools/build_qemu_gfni.sh
python3 tools/run_android_probe.py --qemu patched --name android-detailed-probe --seconds 150
```

The source is pinned to QEMU v11.1.2 commit `4fc49f46dc95d4a27de2509e7fceb2931e91faeb`; the historical patch filename is `patches/qemu11-gfni.patch`. The dependency manifest is `evidence/qemu-build-tools.json`. Meson/ninja are pinned; compiler/host libc are prerequisites. The build script’s native cross-checks require host GFNI, VPCLMULQDQ and AVX512-VNNI/VL support. The Work CPU provides them. Hosts without these features should use the recorded expected digests or another capable native oracle rather than execute unsupported native instructions.

For the additional VNNI hardware comparison, the host executes AVX512-VNNI and the emulator executes equivalent AVX-VNNI operations. This accommodates the Work CPU, which supports AVX512-VNNI but does not advertise AVX-VNNI:

```sh
gcc -O2 -static -o build/vnni-native tools/test_vnni.c
gcc -O2 -static -DEMULATED_AVX -o build/vnni-emulated tools/test_vnni.c
build/vnni-native > evidence/vnni-native.txt
build/qemu11/qemu-x86_64 -cpu max build/vnni-emulated > evidence/vnni-emulated.txt
diff -u evidence/vnni-native.txt evidence/vnni-emulated.txt
```

The tested instruction digests are `fac410b5009f4d4f` (GFNI/VPCLMUL) and `cd09a9370c7cef79` (VNNI). The patch does not claim AVX-512 guest emulation. It has not undergone upstream QEMU review.

The direct-kernel Android probe uses a generated external ramdisk containing original normal-boot platform/dlkm/generic fragments plus an owned override suppressing board-specific early module loading. It never uses the recovery-media slot. It retains original boot-partition UUID identification and AVB/dm-verity setup. This userspace probe uses SeaBIOS direct kernel loading; the separate 130 MiB probe demonstrates UEFI independently. A subsequent local assembler combines UEFI and the compatibility experiment; see the final section. A stable Android desktop and HP boot remain unfinished.

## Build the independent compatibility-partition experiment

```sh
python3 tools/build_compat_probe.py
python3 tools/run_android_probe.py --qemu patched --compat --name android-compat-vnni-probe --seconds 150
```

Outputs are `build/compat-probe/compat.ext4` (64 MiB), `build/compat-probe/recovery-view.qcow2` (small, dependent on the local official recovery), generated owned configuration, and `manifest.json`. This is a local VM disk view, **not a portable raw SSD image**. Google’s original raw recovery remains its unchanged backing image. Original partition extents/GUIDs are preserved; the view adds a new GPT partition beyond them. Execution adds another disposable snapshot, so virtual userdata/checkpoint writes are discarded at shutdown.

The added partition mounts read-only at `/oem`. Owned init configuration explicitly imports stock scripts while suppressing identified firmware/Trusty/board startup actions, selects software HAL processes with private libraries, and uses an explicit diagnostic fstab. Userdata encryption is disabled for this experiment only. Its failed manifest bind mounts remain logged to demonstrate the enforcing-policy restriction; they do not silently succeed or alter original system files.

Evidence now establishes original verified partition mounting, enforcing SELinux, second-stage init, compatibility partition/configuration loading, software security process execution, and replacement boot-control service registration. The boot-control donor must start before checkpoint restoration. `evidence/android-compat-early-boot-hal-probe.log` shows successful fresh virtual userdata formatting/mounting and APEX activation before the next unsupported CPU instruction; the VNNI patch addresses that instruction.

Security-manifest composition before SELinux setup, appropriate enforcing policy, complete software shared-secret registration, credentials, graphics and physical HP support remain outstanding. The scripts intentionally accept no physical block-device output argument. See `REPORT.md` section 13 for current findings and limits.


`tools/analyze_android_probe.py NAME` writes observed milestones to `evidence/NAME-milestones.json`, distinguishing launches from stable services. The current completed `android-compat-vnni-probe` reaches Zygote and attempted SurfaceFlinger starts without an invalid-instruction trap or kernel panic; both processes repeatedly restart because graphics/security integration is incomplete. A separate diagnostic service in the compatibility init attempts to write a service list and recent logcat output to the virtual UART; its opening of `/dev/ttyS0` is denied by enforcing SELinux (`init` reading/writing `serial_device`). Interactive UART input likewise did not produce a shell in this test. The attempt is retained as evidence for the compatibility-policy work; it has no network connection or physical-device access.

## HP diagnostic disk and macOS preparation

The latest standalone disk is `build/hp-diagnostics/gbrunch-hp-diagnostics.img`, 270,532,608 bytes (258 MiB). The current full-test downloadable gzip is `build/gbrunch-hp-full-tests.img.gz` (about 130 MiB); its adjacent `.sha256` file authenticates the compressed file. Follow `HP-START-HERE.md` to write and verify it with macOS `dd` and boot it from HP's F9 menu.

This contains two diagnostic boot options: a visible Debian 6.12 console/inventory and an original Googlebook 6.18 kernel/inventory. Neither starts Android services or includes proprietary Google system partitions. Modules match their respective kernels; no cross-kernel module loading is attempted. The current default expands the Linux inventory into a peripheral-driver/test batch and then uses kexec to start the Google diagnostic kernel. Basic inventory is retained as a fallback. The original Google kernel has no text framebuffer console, so that option collects logs then powers off. The visible Linux option remains at a shell.

Rebuild in the Linux Work environment, using the already prepared private `tools/local` sysroot, GCC and original extracted Ruby kernel/modules:

```sh
python3 tools/prepare_hp_kernel.py
python3 tools/prepare_hp_batch_assets.py
python3 tools/build_hp_diagnostics.py
python3 tools/test_hp_diagnostics.py --mode batch
python3 tools/test_hp_diagnostics.py --mode linux
python3 tools/test_hp_diagnostics.py --mode google
python3 tools/test_hp_diagnostics.py --mode linux --reject-marker
gzip -c -6 build/hp-diagnostics/gbrunch-hp-diagnostics.img > build/gbrunch-hp-full-tests.img.gz
sha256sum build/gbrunch-hp-full-tests.img.gz > build/gbrunch-hp-full-tests.img.gz.sha256
```

The Debian package is fetched from its official pool URL with pinned size and SHA256 in `evidence/hp-diagnostic-kernel-package.json`; unpacking does not install a host kernel. The builder uses dependency-first direct module loading and emits the exact module selection/hashes. EFI GRUB explicitly loads FAT/GPT modules before searching the external volume by UUID. The logger verifies GPT CRCs/disk and partition GUIDs, FAT serial and marker, and requires exactly one matching volume. Other block devices become read-only; only the marked external FAT partition receives logs.

All three QEMU tests passed. Their `evidence/hp-*-usb*.json` records identify test scope. Each uses an owned regular disk-file copy on emulated USB3, UEFI firmware and a separate synthetic internal disk. No HP or host physical disk is accessed. Tests check persisted `COMPLETE.txt`, not just UART output. The deliberately invalid marker is refused.

## Local assembly of the QEMU-only external Android research image

`tools/assemble_external_lab.py` and the owned asset kit implement UEFI boot of the compatibility experiment. The kit includes no Google recovery, kernel, ramdisks or proprietary system image. Original recovery ZIP/raw files are fetched separately from Google, SHA256-checked and retained. The output changes GPT metadata, adds an independent compatibility partition and substitutes EFI boot files in the output view; original system/vendor/super/boot partition bytes retain their original contents and extents. The source recovery is read-only throughout.

Build the kit in the Work environment:

```sh
python3 tools/prepare_external_lab_assets.py
```

For local assembly on macOS, extract `build/gbrunch-external-lab-kit.tar.gz`, install Python 3 and `brew install qemu mtools lz4`, then run in the extracted folder:

```sh
python3 assemble_external_lab.py --download --output Googlebook-lab.img
```

This writes a new regular file, never a physical drive. Allow at least 40 GB of working disk space for the ZIP, extracted recovery and output. The output is about 19.14 GB logical size. Android startup is gated to a QEMU SMBIOS manufacturer until graphics, security and firmware work is complete. Use the separate diagnostics image for HP testing. Standard QEMU lacks CPU instructions required by this recovery; use our tested local emulator patch for the Work environment experiment.

Space-efficient Work environment assembly and test (the QCOW2 depends on the retained official raw recovery):

```sh
PATH="$PWD/build/qemu11:$PWD/tools/local/usr/bin:$PATH" LD_LIBRARY_PATH="$PWD/tools/local/usr/lib/x86_64-linux-gnu" python3 tools/assemble_external_lab.py --assets build/external-lab-assets --recovery-raw downloads/ruby-recovery.raw --output build/external-lab.qcow2 --format qcow2
python3 tools/test_external_lab.py
```

The assembler refuses existing output paths and `/dev` paths. Hash manifests record the source recovery and generated view. Its first-stage ramdisk overrides are independently generated from locally extracted original normal-boot fragments; recovery-mode fragments are excluded. AVB remains enabled for the original logical system partitions. The experimental VM fstab disables userdata encryption pending software-security integration. This configuration is unsuitable for personal data.

The 100-second combined UEFI/USB3 test passed its original-kernel/init acceptance checks without kernel panic; it was deliberately terminated after observation, not shut down by Android. `evidence/external-lab-uefi-usb.json` records the result. `evidence/external-lab-preservation.json` confirms all 30 original GPT records and original system/vendor/super backing bytes remain preserved. This does not establish stable graphics/security/desktop startup.

The latest expanded batch test uses `python3 tools/test_hp_diagnostics.py --mode batch` and passes automatic kexec handoff, both saved passes and shutdown. It runs guided input for only two seconds and skips optional speaker/suspend in its unattended fixture; physical media retains the 40-second input and optional prompts. The production gzip is `build/gbrunch-hp-full-tests.img.gz`, with adjacent checksum; `HP-START-HERE.md` contains its current compressed and raw read-back hashes. Tests verified actual persisted summary/completion, storage read sample, kexec status and emulated NVMe health response.


## Independent vendor/security experiment and original Xe admission

These commands run in the retained Work workspace with its pinned toolchains and original Google recovery. They generate local-only proprietary vendor artifacts; do not upload the generated vendor EROFS/QCOW2 or package it with the public build scripts. `build_vendor_view.py` refuses an existing QCOW2 output. Retain evidence or use a separate owned output directory when repeating the vendor construction.

```sh
gcc -O2 -I tools/sepol311/usr/include -o build/extend-vendor-policy tools/extend_vendor_policy.c tools/sepol311/usr/lib/x86_64-linux-gnu/libsepol.a
python3 tools/build_compat_probe.py
python3 tools/build_vendor_view.py
python3 tools/run_android_probe.py --compat --vendor-view --qemu patched --seconds 120 --name android-vendor-labeled-config-probe
python3 tools/analyze_android_probe.py android-vendor-labeled-config-probe
python3 tools/prepare_original_xe.py
python3 tools/test_original_xe.py
```

The security probe checks actual registration and crashes under enforcing SELinux. The Xe test boots the original kernel with its original modules and staged Meteor Lake firmware on an emulated machine with no Intel GPU. It checks admission only. Source recovery and HP return artifacts remain retained. The new vendor experiment has not yet been incorporated into the external SSD assembler or validated on HP hardware.


## Final physical graphics gate image

`build/gbrunch-hp-final-graphics.img.gz` boots directly into Google's original kernel with the original Xe module closure and pinned Meteor Lake firmware, avoiding the observed i915/kexec failure. The owned static `hp_xe_graphics.c` helper queries engine/memory capabilities, allocates a WC GEM object, creates a VM and render queue, submits MI_STORE_DWORD_IMM plus batch termination, waits with finite sync-object deadlines and checks the returned memory value. This proves command execution only, not shaders or Android.

The display helper acquires DRM master, force-probes connectors, prefers the internal eDP panel and an advertised preferred mode, creates a temporary dumb scanout buffer and presents eight color bars for eight seconds before restoring the prior CRTC. Missing modes are inconclusive; ioctl errors are failures. Physical visibility still needs user confirmation. No mode is invented and external monitors are not reconfigured. Driver-bound device file writes are GPU operations, not filesystem or firmware-update writes.

Before each hardware operation, the identity-gated external FAT logger persists a checkpoint; reports and complete kernel logs are saved afterward. Hard failure before the logger can still lose that run. Both helpers have outer timeouts. A direct-kernel UEFI/USB QEMU test passed module loading, persisted checkpoints/reports, absence-of-GPU failure reporting, unchanged synthetic internal disk and shutdown. Mocked UAPI tests verify command construction, memory-write verification, bind failure, KMS restore and missing-mode branches; they are not GPU emulation. Evidence: `evidence/hp-final-graphics-release.json` and `evidence/hp-final-graphics-helper-mock-test.txt`.

Source: `tools/hp_xe_graphics.c`, `tools/test_hp_xe_graphics.c`, diagnostic builder/init. Xe header snapshot provenance/hash: `evidence/hp-xe-uapi-header.json`. No Google proprietary system/vendor images are included in the public diagnostic image. No Android service or firmware updater is launched.
