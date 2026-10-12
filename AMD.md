# AMD graphics investigation — not bootable AMD support

AMD support is experimental and **not implemented or tested on a laptop**. The existing Intel/HP boot entry and vendor build are unchanged. No AMD modules, firmware, replacement kernel or Android Mesa binaries have been built. No AMD boot entry is exposed yet: it would currently boot an Intel-oriented image without the required graphics driver.

## Exact recovery and source

The locally inspected Lenovo Ruby recovery has kernel version
`6.18.21-android17-5-g3938c8d97142-ab16302624`.
The exact source revision is publicly available:
[Android Common Kernel 3938c8d97142d5cf31543aa96f864a2cf832dda0](https://android.googlesource.com/kernel/common/+/3938c8d97142d5cf31543aa96f864a2cf832dda0).
This is an exact revision, not an assumed nearby tag. Its `bazel/constants.scl`
sets branch `android17-6.18`, KMI generation 5, Clang `r584948c`, Rust `1.91.1.p3`.
The recovery config reports Android compiler build 15323222, Clang 22.0.1
based on `r584948c`, LLVM revision `2d65e4108033380e6fe8e08b1f1826cd2bfb0c99`.
No toolchain has been downloaded or used for an AMD build.

## Plan A preflight — module-local exceptions allowed, platform options blocked

Run this against files extracted locally from your own official recovery:

```sh
python3 tools/build_amd_kernel_modules.py --allow-module-booleans \
  --kernel /path/to/extracted/vmlinux \
  --config /path/to/extracted/kernel.config \
  --out /path/to/new/amd-preflight
```

Use `tools/extract-vmlinux` and `tools/extract-ikconfig` for extraction if needed.
The command first verifies the supplied config against the kernel’s embedded config,
then writes a local JSON report and downloads public source files;
exit **2** means blocked. Despite its provisional builder filename, this tool is
currently a preflight only. It never changes the recovery or kernel config.

At the exact source revision:

- `DRM_AMDGPU` is tristate and can produce `amdgpu.ko`.
- `DRM_AMD_DC` is **bool**; `DRM_AMD_DC_FP` is **def_bool**.
  Neither can be set to `m`. They build display-engine code into amdgpu,
  rather than necessarily adding code to the core kernel. Nevertheless,
  enabling them requires `n -> y`. The approved `--allow-module-booleans`
  exception now permits these two options only with `DRM_AMDGPU=m`. Existing
  built-ins remain protected. DC is required for modern Ryzen display engines.
- `PINCTRL_AMD` and `X86_AMD_PLATFORM_DEVICE` are also **bool**, not
  tristate. The former selects `pinctrl-amd.o` into the built-in pinctrl tree;
  the latter enables AMD ACPI platform-device handling and built-in `clk-fch.o`.
  They are **not** covered by the module-local exception. The full requested
  option set therefore remains blocked. No attempt was made to force them to `m`.
- SimpleDRM is tristate, but the recovery disables `SYSFB_SIMPLEFB`.
  A module alone does not guarantee a UEFI simple-framebuffer device exists.
- `AMD_IOMMU` remains disabled. It has not been established as a mandatory
  prerequisite for basic AMD display; it must not silently be enabled.
- Module signature enforcement is not forced, but `MODULE_SIG_PROTECT=y`.
  Protected symbols/module names and actual runtime admission still need checking.

The local extracted core export table contains **4,501 symbols**: 343 names
starting with `drm_` and 53 with `ttm_`; none starting with `drm_sched`,
`drm_buddy`, `drm_exec` or `amdgpu`. This is the core export table, **not** a
complete combined core/module KMI allowlist. Original module exports must also
be inspected. No AMD import list exists yet, so no AMD CRC match or missing-import
claim can be made. An extracted CRC table is not a substitute for a complete,
matching build `Module.symvers` (addresses/export types/namespaces also matter).

Plan B has not started: the complete Plan A option set stopped on built-in platform
options, not on a demonstrated AMD module ABI failure. There is no basis yet to rebuild
all original modules or claim a replacement kernel is safe.

## Next implementation gates

1. The DC boolean exception is implemented. Determine whether a **graphics-only**
   subset can omit the blocked pinctrl/platform options for a specific laptop.
   They are not direct selects in AMDGPU’s Kconfig, but their absence may break
   other hardware. This is not yet a validated workaround. Run full Kconfig
   resolution with the matching toolchain and inspect **every** resulting difference,
   including selected boolean dependencies and core structure changes. Display-helper
   booleans also need owner/structure audits before granting any further exceptions.
2. Obtain the exact source/toolchain and matching generated headers/export metadata.
   Build AMDGPU and missing helper modules; verify ELF x86_64, exact vermagic,
   imported symbol CRCs, namespaces and signing/protected-symbol restrictions.
   Never force-load mismatched modules.
3. Package only in a separate AMD compatibility variant. Load only after detecting
   PCI vendor `1002`; leave Intel defaults and original system partitions unchanged.
4. Build Android x86_64 Mesa radeonsi/RADV and compatible minigbm AMD backend.
   Audit the Ruby allocator/mapper/composer interfaces before replacing them.
   The existing VM SwiftShader/Cuttlefish graft is useful plumbing, **not** an AMD
   hardware renderer. Linux desktop Mesa packages cannot simply replace Android HALs.
5. Select firmware from the built driver's `MODULE_FIRMWARE` requirements and the
   tester's actual PCI IDs. Pin linux-firmware revision, hashes and license files.
   **Current firmware list: none.** Marketing APU names are insufficient to choose
   all required GC/DCN/PSP/SDMA/VCN/SMU blobs, especially for newer Ryzen AI devices.
6. Only after admission checks, expose **Experimental AMD (untested)** with its own
   compatibility assets, `drm.debug=0x1e`, verbose printk and supported DC logging.
   Verify persistence into GBLOG before asking a tester to boot it.

## Testing and tester logs

Preflight ran on the retained official recovery with the approved exception; it
verified the embedded config and stopped on the two built-in platform options.
The exact public source archive was downloaded and retained in Work. Its SHA256 is
`d9cdb66cf162a1c965d7d10fc52e0189b8be219f43b1e305ce40004e0395b1e9`.
Kconfig/Makefile/script files were extracted for inspection; full Kconfig resolution
and compilation have **not** run. Config-preservation, exception-scope, embedded-config
guard tests and existing GRUB/Windows-launcher regression tests passed.
No AMD QEMU smoke test or hardware test has run: there are no AMD build artifacts
and ordinary QEMU does not emulate an AMD GPU. A future smoke test must report
module admission separately from actual rendering and Intel regressions.

A tester should send the GBLOG bundle plus PCI IDs (`lspci -nnk` from the Linux
toolbox), kernel version/config and AMD build report, complete dmesg including
firmware requests and symbol/signature errors, DRM connector/mode information,
SurfaceFlinger/allocator/composer logs, and Android crash logs. Include the boot
entry selected and laptop model; remove account identifiers before sharing.
If Android never starts, collect Linux toolbox hardware inventory and a photo or
serial capture of early kernel output: GBLOG may not have been mounted yet.

Known gaps: AMD graphics and Android userspace unbuilt; SOF/ACP audio not done;
suspend, sensors, camera, Wi-Fi and firmware selection untested. No compatibility
claim is made for the HP OmniBook or any other AMD laptop.
