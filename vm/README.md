# Windows x86_64 VM research

This is an early QEMU experiment, not a downloadable Googlebook VM or a working Windows launcher.

The intended workflow downloads the official Lenovo Ruby recovery locally, preserves Google's system partitions, and assembles a virtual-device compatibility environment using Android Cuttlefish. No Google recovery or assembled Googlebook image is distributed here.

## First hardware probe

`probe_virtual_gpu.py` builds a small BusyBox initramfs from locally extracted Cuttlefish x86 files and boots its matching kernel under QEMU TCG. It attaches no disks and enables no network. It tests registration of the virtio GPU display and render devices in sysfs; it does not test Android, rendered frames, 3D acceleration, or Windows WHPX.

Tested on the Linux Work host with QEMU 11: Cuttlefish build 16373615, kernel `6.12.74-android16-6-g3ec022196c4e-ab15076761`. The matching virtio GPU initialized and registered `card0`, `card0-Virtual-1`, and `renderD128`. Android kernels rely on userspace device management; this minimal initramfs does not create DRM device nodes automatically.

```sh
python3 vm/probe_virtual_gpu.py \
  --donor /path/to/extracted/cuttlefish-x86 \
  --busybox /path/to/static/busybox \
  --qemu /path/to/qemu-system-x86_64 \
  --work /path/to/new/probe-directory
```

Use `--qemu-data` and `--bios` if QEMU's firmware is not installed at its default paths. The serial transcript is saved as `serial.log`. The donor layout currently follows the retained research extraction, including `boot/kernel` and `vendor_boot/fragment-0-platform-files/lib/modules/`.

## Remaining gates

- Ruby's kernel is Android 17 / Linux 6.18.21. The retained Cuttlefish x86 donor is Android 16 / Linux 6.12.74. Its virtual drivers cannot be loaded into Ruby's kernel because their symbol ABI differs.
- Test Ruby userspace with a matching virtual kernel/module set, or obtain/build virtual drivers matching Ruby's kernel. The successful driver probe does not establish Googlebook compatibility with the donor kernel.
- Assemble and validate allocator, mapper, compositor, EGL, virtual networking and software security components.
- Boot to the actual Googlebook desktop and test input, graphics, networking and persistence.
- Package local preparation, start, log collection and reset for Windows, then validate WHPX on a Windows host. Hardware accelerated virtual graphics is unproven.

Credits: [gbos-vm](https://github.com/skylartaylor/gbos-vm) provides the vendor-grafting model; Android Cuttlefish provides virtual-device components. See the project README for upstream licenses and credits.

## Googlebook userspace experiment

A subsequent local Linux/QEMU test used the matching Cuttlefish kernel/early modules and the existing private Ruby compatibility view. It reached Android second-stage init, mounted the system, activated system APEX packages, and started Zygote and SurfaceFlinger. During a 125-second observation, SurfaceFlinger repeatedly received SIGABRT and restarted Zygote. No working desktop or rendered frame was established.

The physical HP profile also attempted to load Ruby Intel modules into the Cuttlefish kernel, producing expected ABI rejection. A separate VM init profile removes its explicit `insmod` commands. Automatic vendor module discovery and virtual graphics services still need adaptation.

`prepare_android_initrd.py` assembles a private ramdisk from local donor and Ruby extractions, with a caller-supplied compatibility fstab. It also emits a project-owned VM init sidecar. Install that sidecar into a **new local compatibility partition/view** and use `androidboot.init_rc=/oem/init.gbrunch-vm.rc`; a file placed in the initial ramdisk root is lost when Android switches root. This tool does not build the compatibility partition or vendor environment by itself.

`run_local_probe.py` runs a prepared QCOW2 view with disposable writes, captures serial output and a command manifest, and limits runtime. It uses TCG for Linux development. It does not implement Windows WHPX or a graphical user launcher yet. Inputs must be regular local files; never provide host block devices. A normal QEMU exit or timeout does not indicate boot success.

The private Google-derived ramdisks, recovery views and raw transcripts remain in the Work environment, outside this repository.

The separate compatibility-partition init profile was subsequently tested. Android read `/oem/init.gbrunch-vm.rc` successfully. Delayed serial logcat captured the graphics abort: ANGLE's Vulkan initialization fails, `eglInitialize` returns `EGL_NOT_INITIALIZED`, and SurfaceFlinger aborts with `no suitable EGLConfig found`. This establishes a userspace graphics failure in this profile; it does not establish that other startup dependencies are resolved. The next experiment must supply a compatible virtual/software rendering stack rather than reuse the Intel Vulkan path.
