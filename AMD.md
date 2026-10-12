# AMD graphics investigation — not bootable AMD support

AMD support is experimental and **not implemented or tested on a laptop**. The existing Intel/HP boot entry and vendor build are unchanged. AMDGPU has compiled
into a complete driver object with the exact recovery compiler and generated headers.
A separate replacement kernel has compiled successfully, including `bzImage` and
approximately 115 modules. A diskless QEMU boot and module-admission test passed. No bootable
AMD Googlebook image or Android AMD graphics binaries are available yet, and no
physical AMD boot has been attempted. An opt-in AMD GRUB entry is implemented with separate-asset guards; no ready-to-boot AMD assets are distributed.

## Current implementation progress

The complete AMDGPU object (`amdgpu.o`, approximately 25 MiB) compiled with DC/DC_FP
against the recovery’s actual generated headers from `kheaders.ko`. The compiler’s
full version string matches, including Android build **15323222** and LLVM revision.
The pinned public compiler is available on `main-kernel-2026`, at prebuilt repository
commit `4a7d0a5e443c27d8f68fbd46abfab464e1355a69`, directory `clang-r584948c`.

A symbol-presence audit of the object found **937 imports**, including **131 not
exported by the recovery core or its shipped system/vendor modules**. This excludes
`__this_module`, which modpost generates. Some missing symbols are supplied by newly
built helpers (for example the separate AMD XCP helper), but many require core exports:
`kernel_fpu_begin_mask`, `kernel_fpu_end`, `ioremap_wc`, `arch_phys_wc_add`,
`dma_fence_get_status`, several DRM atomic helpers and TTM functions. Rebuilding
helper modules alone does not solve those absent core exports. This audit establishes
an export obstacle; it is not a fabricated CRC match or a runtime admission test.

The approved fallback is a **separate experimental AMD kernel**, from the exact ACK
revision with the recovery config as its base. Its `bzImage` and approximately 115
modules have compiled. It enables real built-in AMD platform options, keeps AMDGPU
modular, enables SimpleDRM/sysfb and turns off export trimming. It also uses
a built-in C binder implementation rather than Rust binder for this first profile.
All resulting config differences are recorded locally. GKI’s protected-export list
is cleared in this experimental kernel; the stock kernel is untouched. The profile
has a different kernel identity. QEMU boot and AMDGPU/helper admission passed; remaining original-module
coverage still needs review; this is not evidence of a complete Android boot.

The stock vendor Vulkan library identifies itself as Mesa **26.1.3** and is Intel-only.
The stock minigbm library exposes Intel backends and a legacy Radeon backend, but
inspection did not find an AMDGPU backend. An Android-compatible AMD allocator and
renderer still need building and validation; native Linux Mesa binaries are unsuitable.

## Exact recovery and source

The locally inspected Lenovo Ruby recovery has kernel version
`6.18.21-android17-5-g3938c8d97142-ab16302624`.
The exact source revision is publicly available:
[Android Common Kernel 3938c8d97142d5cf31543aa96f864a2cf832dda0](https://android.googlesource.com/kernel/common/+/3938c8d97142d5cf31543aa96f864a2cf832dda0).
This is an exact revision, not an assumed nearby tag. Its `bazel/constants.scl`
sets branch `android17-6.18`, KMI generation 5, Clang `r584948c`, Rust `1.91.1.p3`.
The recovery config reports Android compiler build 15323222, Clang 22.0.1
based on `r584948c`, LLVM revision `2d65e4108033380e6fe8e08b1f1826cd2bfb0c99`.
That pinned public Clang 22 toolchain was downloaded and used for the driver object
and separate replacement-kernel builds.

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
- `AMD_IOMMU` was not enabled in this preflight profile. The later isolated
  replacement-kernel profile explicitly enables `AMD_IOMMU=y` as an authorized
  configuration choice; this does not change the stock kernel.
- Module signature enforcement is not forced, but `MODULE_SIG_PROTECT=y`.
  Protected symbols/module names and actual runtime admission still need checking.

The local extracted core export table contains **4,501 symbols**: 343 names
starting with `drm_` and 53 with `ttm_`; none starting with `drm_sched`,
`drm_buddy`, `drm_exec` or `amdgpu`. This is the core export table, **not** a
complete combined core/module KMI allowlist. Original module exports must also
be inspected. The compiled driver import list has now been audited as described above. No stock-kernel AMD CRC match or runtime admission claim has been established.
The replacement kernel has passed the separate module-admission test. An extracted CRC table is not a substitute for a complete,
matching build `Module.symvers` (addresses/export types/namespaces also matter).

The replacement-kernel experiment followed the object audit, which found 131
imports absent from stock exported symbols. Rebuilding a matching kernel was
necessary to provide a coherent export set. This remains a build experiment, not a
claim of a working Android graphics stack.

## Next implementation gates

1. Assess the original module
   inventory. Current filename mapping leaves **470 original module filenames**
   without a rebuilt-module or built-in match. These are not all necessarily needed
   for Android boot; required vendor functionality and external sources still need
   review.
2. Verify ELF architecture, module vermagic, all imported symbol CRCs/namespaces
   and actual module admission against the replacement kernel. Never force-load
   mismatched stock modules or invent CRCs to make them load.
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
The exact public source archive was downloaded and retained in Work. The input
preparer now records a hash manifest of extracted source files, and builders verify
those listed bytes; intentional recovery header overlays are excluded only for
the stock-kernel driver-object experiment. Its SHA256 is
`d9cdb66cf162a1c965d7d10fc52e0189b8be219f43b1e305ce40004e0395b1e9`.
The AMDGPU object build and import audit found 937 imports, of which 131 are absent
from stock exports. The separate `6.18.21-gbrunch-amd` replacement kernel `bzImage`
and approximately 115 modules compiled successfully with the pinned toolchain.
Filename mapping currently leaves 470 original module filenames without a rebuilt
module or built-in match; that count does not establish that every such module is
required. The diskless `tools/test_amd_kernel_qemu.py` module-admission test is
passed using QEMU TCG: the kernel booted and all 13 modules in the AMDGPU
dependency closure loaded successfully, including `amdgpu`. The test activates
the 8250 console with `8250.nr_uarts=1` because the inherited runtime UART count
is zero. Ordinary QEMU does not emulate an AMD GPU, so this establishes kernel
boot and module admission only. No physical AMD boot has occurred. AMD firmware,
Android userspace, minigbm backend and vendor graphics integration remain undone;
there is no claim of a complete Android boot or hardware rendering. All 17 AMD unit checks and five boot-menu unit checks passed. The UEFI
integration script requires explicit private-fixture arguments and cannot run
through generic unittest discovery; it was not rerun for this change.

A tester should send the GBLOG bundle plus PCI IDs (`lspci -nnk` from the Linux
toolbox), kernel version/config and AMD build report, complete dmesg including
firmware requests and symbol/signature errors, DRM connector/mode information,
SurfaceFlinger/allocator/composer logs, and Android crash logs. Include the boot
entry selected and laptop model; remove account identifiers before sharing.
If Android never starts, collect Linux toolbox hardware inventory and a photo or
serial capture of early kernel output: GBLOG may not have been mounted yet.

Known gaps: a bootable AMD Googlebook package is not yet assembled; AMD Android userspace unbuilt; SOF/ACP audio not done;
suspend, sensors, camera, Wi-Fi and firmware selection untested. No compatibility
claim is made for the HP OmniBook or any other AMD laptop.

## Reproducible Linux build stages

Install Linux build prerequisites (`make`, GCC, flex, bison, m4, bc, OpenSSL
headers, libelf headers, pkg-config and standard compression tools). These are
Linux build scripts, not macOS-native compiler launchers.

```sh
python3 tools/prepare_amd_build_inputs.py --work /path/to/amd-inputs
python3 tools/build_amd_driver_objects.py \
  --source /path/to/amd-inputs/source \
  --clang /path/to/amd-inputs/clang-r584948c \
  --kernel /path/to/recovery/vmlinux --config /path/to/recovery/kernel.config \
  --kheaders /path/to/recovery/system_dlkm/lib/modules/kheaders.ko \
  --out /path/to/amd-object-report
```

This stage makes a driver **object**, not an installable module. Use
`tools/audit_amd_imports.py` with the extracted core export JSON and original
module directories to reproduce the presence audit. Do not confuse this with KMI
certification or a successful boot.

For a replacement kernel, use a **fresh full source tree**, not the header-overlaid
object-build tree:

```sh
python3 tools/prepare_amd_build_inputs.py --full-source --work /path/to/amd-full-inputs
python3 tools/build_amd_replacement_kernel.py \
  --source /path/to/amd-full-inputs/source \
  --clang /path/to/amd-full-inputs/clang-r584948c \
  --kernel /path/to/recovery/vmlinux --config /path/to/recovery/kernel.config \
  --original-modules /path/to/recovery/system_dlkm/lib/modules /path/to/recovery/vendor_dlkm/lib/modules \
  --out /path/to/amd-kernel-output --jobs 2 --compile
```

The tool records all resolved config changes and, after a successful build, original
module filenames not rebuilt and those covered by built-in implementations.
`--resume` accepts only a directory marked as an owned AMD build. Building kernel
assets does **not** install them, rewrite the SSD, or supply the AMD Android vendor
stack. Wait for an explicitly validated test package before attempting a laptop boot.

## Current build-environment limit

The current 32 GB build workspace has less than 300 MB free after preserving
the recovery and compiled artifacts. It cannot presently accommodate an Android
Mesa/LLVM/sysroot build. The compiled kernel is retained for further work, but
firmware and Android HAL integration must be completed in a larger build workspace
before producing a useful AMD laptop trial. No Intel assets have been replaced.

Reproduce the diskless smoke test after building (requires QEMU and a statically
linked x86_64 BusyBox):

```sh
python3 tools/test_amd_kernel_qemu.py \
  --build /path/to/amd-kernel-output --busybox /path/to/busybox \
  --qemu /path/to/qemu-system-x86_64 --work /path/to/new-smoke-report
```

The test attaches no host disks or network. It records each real `insmod` result,
requires all dependencies and AMDGPU to load, then powers off. A passing result
does not demonstrate AMD rendering. A sanitized result is retained in
[docs/amd/replacement-smoke-result.json](docs/amd/replacement-smoke-result.json).
