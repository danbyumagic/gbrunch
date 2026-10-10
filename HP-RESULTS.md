> Historical research/build log. Earlier statements describe that stage of development. See [README.md](README.md) for current status. Referenced private recovery files and raw device logs are intentionally not published.

# First physical HP results

The uploaded FAT partition was retrieved from the user's Filebin link and extracted without mounting it. Its original gzip and FAT copy remain in `downloads/hp-after-tests.fat.gz` and `extracted/hp-after-tests.fat`; logs are retained under `extracted/hp-logs/GBRUNCH-LOGS`.

Two Linux batches and two original-Google-kernel passes have completion markers. The extended Linux batches contain their final completion marker, and both kexec records show successful loading. This establishes that the experimental diagnostic boot, USB logging and original Google kernel work on this physical laptop. Android userspace and a Googlebook desktop were not tested by this diagnostic image.

## Confirmed hardware

| Component | Actual HP evidence |
| --- | --- |
| Model/board | HP Envy x360 2-in-1 Laptop 15-fe1xxx; board 8C4F, revision 92.30 |
| BIOS | Insyde F.08 |
| CPU | Core Ultra 7 155U, model 170, 12 cores/14 threads |
| Graphics | Intel 8086:7d45, HP subsystem 103c:8c4f; i915 bound under Linux 6.12 |
| Wi-Fi | Intel 8086:7e40, subsystem 8086:0094; iwlwifi/iwlmvm and scanning work |
| Bluetooth | Intel USB 8087:0033; hci0 registered; pairing untested |
| Audio | Intel 8086:7e28, subsystem 103c:8c4f; SOF IPC4 firmware 2.12.0.1 booted, card registration incomplete |
| Camera | Quanta USB 0408:5465, HP Wide Vision 5MP; visible and IR capture nodes delivered frames |
| I2C HID | ACPI devices SYNA32EF:00 and ELAN2513:00; drivers deferred in diagnostic image |
| Sensors | ISH/HID/IIO exposed acceleration, gravity and gyro readings |
| Internal NVMe | KIOXIA KBG50ZNV512G; read-only SMART: no critical warning/media errors, 100% spare, 7% used, 303 K |
| External bridge | ASMedia 174c:55aa; log writes and read-only 16 MiB sample succeeded |

The camera differs from the previously researched owner's USB device. That earlier machine's marketing model did not establish this user's exact configuration. PCI/USB/subsystem records are retained in `evidence/hp-confirmed-device-ids.json`.

## Test interpretation

Actual GFNI/VPCLMUL and AVX-VNNI execution produced the expected digests in both Linux batches. The physical CPU supports the instructions that blocked stock QEMU execution of Googlebook userspace.

i915 initialized the Meteor Lake graphics hardware, enabled GuC submission on both GTs and detected the internal 1920×1080 display. The GPU smoke test stopped at `GEM_PWRITE: Operation not supported`, before it submitted any GPU command. This is a legacy probe API limitation, not evidence of failed rendering hardware. The helper source now falls back to modern `GEM_MMAP_OFFSET`; that correction compiles but has not been run on this HP. An additional GSC proxy timeout corresponds to the omitted `mei_gsc_proxy` module.

Input-event reports were empty because the original module selection omitted `evdev`. The I2C-HID drivers also deferred, with Meteor Lake pinctrl absent. The updated source selection adds evdev, pinctrl, IDMA64 and PCI DesignWare support, and the event helper explicitly reports an inconclusive result when no event nodes exist. Touchpad, touchscreen and tablet event behavior are not established by the first reports.

SOF successfully detected HDA codecs and booted its IPC4 DSP firmware, but `skl_hda_dsp_generic` remained deferred and ALSA reported no cards. The diagnostic closure omitted `snd_soc_hdac_hda`/`snd_soc_hda_codec` bridge modules; these are now selected in the source. This diagnosis does not guarantee speakers will work after the missing modules are present. Codec, amplifier firmware/quirks and actual audible output remain acceptance checks.

One Linux run entered s2idle and returned successfully, with a `SUSPEND_RETURNED status=0` record. Kernel log timestamps show about 5.2 seconds between entry/exit, so the record does not prove the intended 20-second wake interval, deep power savings, or all peripherals working after resume. Its resumed input report is inconclusive due to missing evdev.

The successful Wi-Fi scans establish radio/firmware/scan behavior, not association or internet access. Both camera capture nodes delivered five frames each; metadata nodes were correctly skipped. Bluetooth pairing and USB4 accessory transfers remain untested. An absent regulatory database and optional Intel Wi-Fi debug firmware appear in the logs; the latter is not the main radio firmware and did not prevent scanning.

## Implication for Googlebook compatibility

Google's original 6.18 kernel already boots on this physical HP and accesses the external USB drive. Its original vendor `xe.ko` includes the exact GPU alias `8086:7d45`, requests Meteor Lake firmware and advertises a default force-probe setting of `*`. The metadata is retained in `evidence/hp-original-xe-metadata.txt`.

This is a promising native-kernel GPU route: supply matching Meteor Lake firmware and evaluate the original Xe module/dependencies rather than assume this device is absent from Google's driver. Metadata alone does not prove firmware-version compatibility, successful Xe initialization, Android allocator/composer support or display output. The original recovery's missing Meteor Lake firmware, software security/VINTF/SELinux composition and generic vendor support remain work items.

The source fixes have been compiled/syntax-checked, but a revised image has not been published or physically validated. The already uploaded/downloadable diagnostic image remains the version used for these logs. No further HP run is required merely to repeat inventory; the retained logs and ACPI tables support the next offline integration work.


## Returned Xe diagnostic results

Both Linux and original-Google-kernel passes completed and saved logs. All 13 original Xe modules loaded, but the module's successful insertion did not establish PCI probe success. Xe recognized Meteor Lake/U 8086:7d45 and loaded DMC v2.23, then attempted GuC 70.53.0. GuC MMIO request 0x4100 received no reply, uC initialization timed out and the PCI probe failed with -110. The GPU remained unbound in the Google pass, with no usable DRM graphics device.

Linux i915 successfully submitted and completed the corrected GPU no-op test through GEM_MMAP_OFFSET. This proves that submission path, not Mesa/Vulkan or Android composition. The corrected module selection now exposes SYNA32EF 06CB:CEE7 touchpad and ELAN2513 04F3:42F8 touchscreen/stylus input nodes.

The failing Xe pass follows an active i915 pass using kexec. Residual GPU/firmware state and firmware-version compatibility are competing possibilities; neither is proved. The next controlled test requires no reflash: power off, boot UEFI USB and select option 2 directly, bypassing Linux and kexec. A cold boot failure would justify inspecting exact GuC firmware/driver requirements and trying a pinned alternative firmware; do not infer from this timeout that Intel hardware is unsupported.

Retained source: downloads/hp-xe-after-tests.fat.gz, extracted/hp-xe-after-tests.fat and extracted/hp-xe-logs. Structured evidence: evidence/hp-xe-first-physical-results.json.


## Cold/direct boot of original Google kernel with Xe

Returned image SHA256 75131fb31f8d3dfaa06a8084b1761dc6a656425a8d660dc9d993564918ef5f47 contains a new completed original-kernel run, 20261008-010710-google. Xe initializes successfully and binds PCI 0000:00:02.0; /dev/dri/card0 and renderD128 exist. Both GTs select GuC 70.53.0 and the previous GuC initialization timeout is absent. This strongly implicates the i915-to-Xe kexec handoff in the earlier failure; the exact reset/state mechanism remains unproven. Native Google/Xe experiments should boot directly from UEFI, bypassing the i915 batch.

Remaining observed error: HuC authentication via GSC fails with 0x100d/-EIO. This does not abort overall Xe initialization, but video/media capability is not established. The eDP connector is enabled with DPMS On, yet status is unknown and its mode list is empty in the saved snapshot. No Xe rendering submission, modeset/frame presentation or Android compositor was tested. Next gate: an owned Xe render/connector diagnostic followed by native minigbm/DRM-composer validation. Preserve these distinctions when reporting progress.

Returned gzip, FAT image and extracted logs are retained at downloads/hp-xe-coldboot-logs.fat.gz, extracted/hp-xe-coldboot.fat and extracted/hp-xe-coldboot-logs. Structured results: evidence/hp-xe-coldboot-results.json.


## Physical Xe rendering and display gate passed

Final returned logs (SHA256 3fcd5701523cbcf10d514324e4b2ab584c05bc3afbb058defebd84e55f1672e2), run 20261008-013016-google, show successful original-kernel Xe 1.1.0 initialization, render-engine submission and the exact GPU-written expected value 0x47584252. The helper returned zero. A forced connector probe resolves the earlier empty-mode snapshot: eDP is connected and advertises 1920x1080 60Hz and 40Hz modes. KMS accepted the color-bar framebuffer/modeset and the user confirmed visible bars. The run saved its after-graphics-checks checkpoint and COMPLETE marker.

These observations establish GPU command execution and native panel scanout on the HP under the original Google kernel. They do not establish shaders, Mesa/Intel Vulkan, ANGLE/EGL, minigbm buffer allocation or Android compositor startup. Previous-display restoration failed with ENOENT after successful bars; the helper reported the warning and the diagnostic proceeded to shutdown. Future presentation tests should treat an unavailable previous framebuffer as a separate cleanup condition rather than assuming it can be restored. HuC authentication still fails with GSC 0x100d/-EIO; media capability remains open.

The next gate is native Android graphics/security integration with direct UEFI boot, preserving the original Google system partitions. Returned gzip, FAT and extracted logs remain retained. Structured evidence: evidence/hp-final-physical-graphics-results.json. Only rebuildable compiler intermediates and a disposable Xe-admission initrd were removed to make room for the returned artifacts; original recoveries, extracted partitions, emulator binaries and HP logs remain.

## First full Android image experiment

Native Xe is now integrated into the Android first-stage ramdisk. Direct
UEFI/USB3 QEMU startup and actual independent FAT log recovery pass, including a
boot using the HP's identifying SMBIOS strings. The local Mac build kit fetches
Google's official recovery and produces a self-contained sparse RAW image;
Google system partitions remain unchanged and the derived vendor stays local.
The next physical test is Android allocator/composer/display startup on the HP.
No Android desktop, shader rendering, audio or connectivity success is claimed.
Logs use GBLOG, partition33,256 MiB; the Mac need not mount it to capture it.
