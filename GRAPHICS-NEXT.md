> Historical research/build log. Earlier statements describe that stage of development. See [README.md](README.md) for current status. Referenced private recovery files and raw device logs are intentionally not published.

# Graphics investigation

The current original-kernel QEMU configuration uses `-vga none` and exposes no graphics device. Ruby kernel configuration has CONFIG_DRM_VIRTIO_GPU unset. Its Xe driver is supplied as an external vendor module, not an in-tree configured driver. Current allocator crashes therefore cannot diagnose physical HP graphics compatibility.

The original vendor uses minigbm allocator/mapper, drm_hwcomposer HWC3, ANGLE EGL and Intel Vulkan. Its minigbm library contains both backend_i915 and backend_xe and the Xe device-query path. All 13 original Xe modules passed actual original-kernel admission. Meteor Lake firmware has been staged; GPU binding/display/rendering remains untested.

Next gates:

1. Capture first allocator/SurfaceFlinger errors plus actual /dev/dri nodes under enforcing SELinux. Expanded compatibility UART diagnostics implement this without changing Google system partitions.
2. For QEMU, produce a compatible VirtIO GPU module closure for the exact 6.18.21 Google kernel (matching symbol versions/config). The retained Cuttlefish 6.12 modules cannot simply be loaded. Then test a virtual GPU and compatible minigbm/DRM composer/EGL path, following gbos-vm's actual graphics graft rather than assuming its ARM modules fit x86.
3. For HP, combine original Xe and its firmware into a diagnostic-only boot that records GPU binding, firmware initialization, DRM connectors/modes and a rendering submission. Include corrected input/audio modules and persistent logs. This hardware test should precede full Android startup.
4. Once a GPU is exposed, verify allocator, composer, Intel Vulkan/ANGLE, SurfaceFlinger, and a visible frame individually. VM virtual graphics validates Android wiring, not Intel hardware acceleration.

Do not redistribute locally generated proprietary vendor views. Source recovery/system partitions remain preserved. No new physical test image is ready from this investigation yet.
