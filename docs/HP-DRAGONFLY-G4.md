# HP Dragonfly G4 profile (board 8B63)

Status: **Android desktop reached on hardware (2026-10-31).** On an HP Dragonfly G4 (i7-1355U, 16 GB,
BIOS 01.12.01) booted from a 128 GB USB stick, setup completed and apps ran. Xe graphics with
`adlp_*`/`tgl_huc` firmware, AX211 Wi-Fi and Intel Bluetooth firmware loaded. Responsiveness is limited by
USB-stick I/O (iowait dominated; CPU mostly idle).

Required xe display options, now added to the kernel command line by the profile:
`xe.enable_psr=0 xe.enable_dpt=0 xe.enable_fbc=0`. Without them the eDP primary plane repeatedly logged
`[CRTC:148:pipe A][PLANE:33:plane 1A] fault (CTL=0x94101000, ...)` (Y-tiled XRGB8888 through DPT), the panel
went black and the cursor disappeared while Android kept running. With all three set, no plane faults
occurred. Which option is strictly needed has not been isolated; DPT is the primary suspect.

## Hardware and expected support

| Device | ID (from the target) | Recovery support | Expectation |
| --- | --- | --- | --- |
| CPU | Core i5-1335U / i7-1355U (Raptor Lake-U) | AVX2, GFNI, AVX-VNNI present | OK |
| GPU | Iris Xe `8086:a7a1` | `xe.ko` alias A7A1 | Works with `adlp_dmc`, `adlp_guc_70`, `tgl_huc` (added) and `xe.enable_psr=0 xe.enable_dpt=0 xe.enable_fbc=0` |
| Wi-Fi | AX211 CNVi `8086:51f1`, sub `8086:0094` | iwlwifi alias 51F1, max API 89 | Firmware loads on hardware: `iwlwifi-so-a0-gf-a0-89` + `.pnvm` (added) |
| Bluetooth | `8087:0033` | btusb/btintel | `ibt-0040-0041` loads on hardware; pairing untested |
| NVMe | MAXIO MAP1202 `1e4b:1202` | built in | OK (no VMD) |
| Keyboard / touchpad | i8042 / SYNA310F I2C-HID | built in | OK |
| USB Ethernet (dock) | RTL8153 `0bda:8153` | r8152 + firmware | OK |
| Audio | ALC245 via SOF `8086:51ca`, 2 DMICs | alc269 has the 103c:8b63 quirk; SOF firmware added by the profile | HDMI output works; no 3.5 mm jack on this model |
| Speakers | 4x CS35L41 on SPI0 (`CSC3551`, full `_DSD`) | no serial-multi-instantiate / snd-hda-scodec-cs35l41; required SPI symbols not exported by GKI | Not working: needs out-of-tree modules plus a shim |
| Camera | IPU6EP `8086:a75d`, hi556 + OVTI00AB, INT3472 | camera HAL is IPU7-only | Not working: use a USB UVC camera |
| Hotkeys | intel_hid, hp_wmi | neither present | Some Fn keys missing |

## Build a Dragonfly asset directory

`tools/prepare_profile_assets.py` derives a new asset directory from an existing kit.
The source kit stays read-only. The tool downloads pinned linux-firmware files and checks their SHA-256 values.
It needs `python3` and e2fsprogs (`debugfs`, `e2fsck`); the v0.3 toolbox has both.
The e2fsprogs clock is fixed with `E2FSPROGS_FAKE_TIME`, so the derived `compat.ext4` is byte-reproducible
(`a341d089...e542` from the V7 image with e2fsprogs 1.47.2). The tool refuses any other result.

The v0.3 trial/installer only accept the V7 `compat.ext4` hash. This branch adds a reviewed hash list
(`COMPAT_HASHES` in `tools/dualboot_installer.py`). The ISO's own copies are read-only, so the updated
modules are run from GBWORK through `GBRUNCH_SOURCE_OVERRIDE` in `trial.py`.

In the Linux toolbox, with GBWORK mounted and internet connected:

```sh
work=$(findmnt -nr -S LABEL=GBWORK -o TARGET | head -n1)
# $work/profile-tools: prepare_profile_assets.py googlebook_boot_menu.py dualboot_installer.py toolbox_source.py
#                      and toolkit/live/root/opt/gbrunch/trial.py from this branch
python3 $work/profile-tools/prepare_profile_assets.py \
  --assets /opt/gbrunch/assets --output $work/assets-dragonfly-g4 \
  --firmware-cache $work/profile-firmware-cache
sudo python3 /opt/gbrunch/source/assemble_native_android.py --download \
  --cache $work/recovery --assets $work/assets-dragonfly-g4 \
  --format qcow2 --output $work/recovery/source.qcow2
sudo env GBRUNCH_SOURCE_OVERRIDE=$work/profile-tools python3 -u $work/profile-tools/trial.py
```

The trial copies `grub.cfg` from the assembled source, so its default entry admits
`HP / HP Dragonfly 13.5 inch G4 Notebook PC / 8B63`.

Internal-disk installation through the ISO menu still uses the ISO's V7-only checks; it has not been adapted.

## Alternative: raw image without the toolbox ISO

`assemble_native_android.py --format raw` (shipped in the asset directory) builds a directly bootable disk
image on any Linux host with `qemu-system-x86`, `qemu-utils`, `mtools` and `lz4`:

```sh
python3 assets-dragonfly-g4/assemble_native_android.py --recovery-raw ruby-recovery.raw \
  --assets assets-dragonfly-g4 --cache assemble-cache --format raw --output googlebook-dragonfly.img
sudo dd if=googlebook-dragonfly.img of=/dev/sdX bs=4M status=progress conv=fsync
```

The raw image keeps the recovery's 4 GiB **unformatted** userdata. Before the first boot, create a larger
userdata partition in the free space after the image and format it exactly as the trial does
(`mke2fs -t ext4 -b 4096 -I 512 -i 16384 -m 0 -O ...casefold...,quota,project,verity -E encoding=utf8-12.1 -M /data`).
Rename the original partition (for example `userdata_small`) so only one partition is named `userdata`.
Observed failures otherwise: unformatted userdata stops `/data` from mounting; 4 GiB fills up during
first boot (ENOSPC), and the resulting NetworkStatsService NullPointerException restarts system_server repeatedly.
Crash counters then persist in `metadata`/`misc`, and RescueParty later attempts FACTORY_RESET. Restore those two
partitions from the image when recovering a disk that has been through such a loop.

## First boot checklist

1. BIOS (F10): Secure Boot off, USB boot on. This unit already reports Secure Boot disabled and no VMD.
2. Connect the USB-C RTL8153 Ethernet adapter; it is the most likely working network path.
3. Allow three minutes, then return to Linux and collect the GBLOG `Android-Logs` directory.
4. Check `dmesg` for: `GuC firmware i915/adlp_guc_70.bin`, `loaded firmware version 89` for iwlwifi, and xe binding to `0000:00:02.0`.

## Known gaps and next work

- Display density: `init.gbrunch.rc` sets `qemu.sf.lcd_density 160` for the 15.6" 1080p HP. The Dragonfly is 13.5" 1920x1280 (about 168 dpi); 160 is usable, though text may look small.
- Audio: **HDMI audio output works (physical test 2026-11-01).** Required pieces:
  1. Kernel: `snd_intel_dspcfg.dsp_driver=3` (otherwise `snd_soc_avs` claims `8086:51ca` and fails on the missing
     `intel/avs/adl/dsp_basefw.bin`). Also needed: `snd_sof_intel_hda_generic.dmic_num=2 hda_model=auto`, overriding Ruby's
     `modules.options` (`alc-2024y-chromebook dmic_num=4`). SOF IPC3 `sof-rpl.ri` + `sof-hda-generic-2ch.tplg`
     from Debian `firmware-sof-signed` 2026.09.2-1 go in `/oem/firmware`, because `firmware_class.path=/oem/firmware`
     hides `/vendor/firmware` from direct loads.
  2. DRAS: there is no `ro.boot.product.hardware.id`, so DRAS cannot resolve a SKU/model ("Both card_name, model should
     be provided") and reads the fallback `/vendor/etc/{audio_config,mixer_paths,volume_curves}.xml`. The profile adds
     those three files to the locally derived GBVENDOR. A patch to the tool VM script adds them, and must start from the
     LAST copy of `payload/native_vendor_in_vm.py` in the multi-archive tool initrd. Patching the first (older) copy
     dropped the graphics memfd and shell rules: the panel went black and the launcher crashed.
  3. `audio_config.xml`: sections with `JackDev` also need `JackSwitch` (the error is "missing field `JackSwitch`").
     The Dragonfly has no 3.5 mm jack, so only InternalMic (PCM 6), Speaker (PCM 0) and HDMI1-3 (PCM 3-5) are listed.
  Still missing: internal speakers (CS35L41 x4 need out-of-tree modules), and the internal microphone recording is untested.
- Charging indicator: Android sees only `BAT0`. Ruby's vendor modules ship ACPI `battery.ko` but not `ac.ko`
  (`Unable to find a module for acpi:ACPI0003`), so `AC powered` stays false. This needs an out-of-tree `ac.ko`
  built for the GKI android17-6.18 KMI, the same build environment as the speaker modules.
- External display: HDMI to a 1920x1080 TV works as an extended display. Booting with HDMI attached was not
  re-tested after the GBVENDOR policy fix.
- Speakers: see the GKI export analysis in the profile notes. A shim must instantiate the four SPI amps through `spi_new_device`.
- Do not publish `acpi/MSDM` from a hardware inventory; it contains the Windows product key.
