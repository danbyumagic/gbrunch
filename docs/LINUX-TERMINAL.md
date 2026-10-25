# Googlebook Linux terminal stuck on loading

This refers to Googlebook's Linux VM application, not the XFCE terminal in the live toolbox. A loading indicator alone does not identify the fault.

## Investigation

The original recovery and compatibility environment need separate inspection. Candidate failures include:

- Missing/inaccessible `/dev/kvm` or disabled firmware virtualization.
- Android Virtualization Framework service/APEX startup, SELinux access or device labels.
- Missing virtual socket, TAP/tun or VM networking support.
- Original vendor security/VM dependencies changed by the compatibility graft.
- Initial Linux image download, extraction, storage capacity or network access.
- Guest startup or app/service crashes after download.

Do not enable random properties, grant broad SELinux permissions, replace the launcher, reset app data or redownload large guest images before collecting evidence. Some protected VM requirements differ from ordinary KVM; ordinary virtualization support does not establish protected-VM support.

The compatibility logger now adds bounded virtualization snapshots at its first and last scheduled captures: KVM/vsock nodes, CPU virtualization flags, selected properties/processes/APEX state, package names, service dump and filtered logcat. Existing size/time budgets apply. These are source changes, not yet deployed to the HP. No terminal fix is claimed without live evidence.

For an on-device test, keep the normal logger running, open the terminal, wait for its loading state, and collect GBLOG afterward. Record whether it displayed download progress and whether networking otherwise worked. Redact account/network details before sharing. The logger does not read guest disks, home directories or terminal session contents.

## Findings from the pinned Ruby recovery

Direct inspection of the verified recovery found:

- `CONFIG_KVM=y`, `CONFIG_KVM_INTEL=y`, `CONFIG_VHOST_VSOCK=y`, `CONFIG_TUN=y`, and x86 pKVM options enabled. Missing KVM kernel compilation is not established as the cause. Actual firmware availability, device permissions and service access still need checking.
- `/system/apex/com.google.android.virt.apex` contains the AVF services and `VmTerminalAppGoogle.apk`. Its runtime APEX is `com.android.virt`; the app package is `com.android.virtualization.terminal`.
- `virtualizationservice` is a lazy AIDL service declared disabled/oneshot. Those declarations are normal and are not evidence of a bug. `vmnic` supplies a separate VM-networking service.
- Vendor properties advertise normal and protected VM support; GBRUNCH's command line explicitly disables advertised protected support. Do not change that to true without establishing actual protected-VM capability. Vendor property presence does not prove the final runtime property values.
- The terminal APK contains a Ferrochrome download base `https://dl.google.com/android/ferrochrome/5100000` and `images.tar.gz` strings. This establishes a download dependency, not its exact runtime URL or whether the HP downloaded it successfully.

Android 17 AVF's public framework reads `HypervisorProperties.hypervisor_vm_supported()` and `hypervisor_protected_vm_supported()`, defaulting to false when absent. The corresponding Rust helper also defaults to false. Runtime properties, `/apex/com.android.virt/bin/vm info`, service state, app crash/error logs and guest/download progress are therefore useful first evidence. Do not infer a missing property solely from its absence in GRUB: this vendor also sets properties.

Sources: [VirtualMachineManager](https://android.googlesource.com/platform/packages/modules/Virtualization/+/refs/heads/android17-release/libs/framework-virtualization/src/android/system/virtualmachine/VirtualMachineManager.java), [hypervisor_props](https://android.googlesource.com/platform/packages/modules/Virtualization/+/refs/heads/android17-release/libs/hypervisor_props/src/lib.rs). Public branch code supports the diagnosis strategy; it is not proof that every shipped Google binary matches that branch exactly.
