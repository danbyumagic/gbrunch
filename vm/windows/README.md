# Windows VM launcher research

**This is not a ready-to-use Googlebook VM download.** The Linux/QEMU profile has visibly rendered the boot animation. Setup, the desktop, keyboard/mouse, networking and Windows/WHPX have not been validated. The current guest networking is disabled. This launcher is for development with an already assembled local VM, not the nontechnical release package.

The eventual package should download the official recovery from Google, build the compatibility environment locally, and offer Prepare, Start, Logs and Reset buttons. That preparation flow and bundled runtimes are still pending. No proprietary images, kernels or ramdisks are included here.

## Local prepared assets

The launcher requires 64-bit Windows on an Intel/AMD processor, Python **3.11 or newer**, QEMU with WHPX, Windows Hypervisor Platform enabled, and virtualization enabled in firmware. It does not enable Windows features or change firmware settings. A machine without the guest's required CPU instructions may fail even when virtualization is available.

Keep the locally assembled `kernel`, `initrd.gz`, `cmdline.txt` and `base.qcow2` in one directory. The base must be a **standalone QCOW2**, flattened from the locally built backing chain. Do not copy a QCOW2 whose backing files point to Linux paths. Keep the original recovery downloads intact and do not redistribute the assembled base. Windows and Linux QEMU versions need to be compatible with the selected QCOW2 features.

Create a local manifest:

```powershell
py -3 make_manifest.py --kernel .\prepared\kernel --initrd .\prepared\initrd.gz --cmdline .\prepared\cmdline.txt --disk .\prepared\base.qcow2 --output .\prepared\vm.json
```

Inspect the launch command without starting the VM or creating files:

```powershell
py -3 launch.py --manifest .\prepared\vm.json --qemu "C:\Program Files\qemu\qemu-system-x86_64.exe" --dry-run
```

Start an experimental disposable trial:

```powershell
py -3 launch.py --manifest .\prepared\vm.json --qemu "C:\Program Files\qemu\qemu-system-x86_64.exe"
```

The launcher verifies hashes for the kernel, ramdisk and command-line file; checks the base with `qemu-img`; rejects host device paths, external QCOW2 data files and nonportable backing chains; and records the command, serial output, QEMU errors and exit result in a dated `prepared/logs/` directory. No physical disks are passed to QEMU. Closing the VM ends the trial; default trial writes are discarded.

`--persistent` keeps guest changes in a separate `prepared/userdata.qcow2`, leaving the prepared base intact. Back up that overlay before experiments. The launcher never automatically deletes it. Resetting saved guest data is not yet a packaged user flow.

WHPX is explicit: a failed acceleration startup is logged, and the launcher does not silently switch to TCG. `--accel tcg` is a developer-only option; the research Linux QEMU includes additional x86 instruction emulation patches, so an arbitrary stock TCG build may fail on Ruby userspace. `--headless --seconds 600` supports bounded developer tests; it does not establish boot success.

The virtual keyboard/tablet devices are included as candidates. Their Android behavior remains unverified. Networking and accelerated virtual 3D are not implemented in this launcher. The displayed graphics remain the guest software-rendering profile.
