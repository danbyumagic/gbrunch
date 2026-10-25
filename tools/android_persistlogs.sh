#!/system/bin/sh
# Owned compatibility logger. Write directly to GBLOG, never through /data.
export PATH=/system/bin:/system/xbin
umask 077
ulimit -f 8192
base=/oem/logs/Android-Logs
mkdir -p "$base" || exit 1
stem="run-$(date +%Y%m%d-%H%M%S)-$$"
run="$base/$stem"
suffix=0
while ! mkdir "$run" 2>/dev/null; do
    [ -e "$run" ] || exit 1
    suffix=$((suffix + 1))
    run="$base/$stem-$suffix"
done
status="$run/status.txt"
exec 2>>"$run/logger-stderr.txt"
echo "GBRUNCH_LOGGER_V4 started $(date) pid=$$" >> "$status"
id >> "$status" 2>&1
cat /proc/mounts > "$run/mounts.txt"
cat /proc/cmdline > "$run/cmdline.txt"
df -k /oem/logs > "$run/log-space.txt"
sync
budget_kib=24576
free_kib=$(awk 'END {print $4}' "$run/log-space.txt")
case "$free_kib" in
    ''|*[!0-9]*) ;;
    *)
        if [ "$free_kib" -lt 8192 ]; then
            echo "LOW_LOG_SPACE freeKiB=$free_kib; preserve existing logs" >> "$status"
            sync
            exit 0
        fi
        available=$((free_kib - 8192))
        [ "$available" -ge "$budget_kib" ] || budget_kib=$available
        ;;
esac
echo "CAPTURE_BUDGET_KiB=$budget_kib" >> "$status"

capture() {
    name=$1
    shift
    used=$(du -sk "$run" 2>/dev/null)
    used=${used%%[!0-9]*}
    if [ "${used:-0}" -ge "$budget_kib" ]; then
        echo "BUDGET_SKIP $name runKiB=$used" >> "$status"
        return 0
    fi
    tmp="$run/$name.partial"
    /system/bin/timeout 8 "$@" > "$tmp" 2>>"$run/commands-stderr.txt"
    code=$?
    bytes=$(wc -c < "$tmp")
    echo "$(date) $name exit=$code bytes=$bytes" >> "$status"
    # Preserve useful partial output even if a command timed out or failed.
    # Every capture has a unique name; never overwrite a previous snapshot.
    if [ -s "$tmp" ]; then
        mv "$tmp" "$run/$name"
    else
        rm -f "$tmp"
        echo "EMPTY_CAPTURE $name (earlier captures retained)" >> "$status"
    fi
    sync
}

capture startup-kernel.txt dmesg
capture startup-process-labels.txt ps -AZ
capture startup-logcat.txt logcat -b all -d -v threadtime
logcat -b all -v threadtime -f "$run/live-logcat.txt" -r 1024 -n 3 &
live=$!
echo "LIVE_LOGCAT pid=$live rotation=3x1024KiB" >> "$status"
trap 'kill "$live" 2>/dev/null; echo LOGGER_STOPPED >> "$status"; sync' EXIT

for n in 01 02 03 04 05 06 07 08 09 10; do
    echo "SNAPSHOT $n $(date) uptime=$(cat /proc/uptime)" >> "$status"
    capture "$n-properties.txt" getprop
    capture "$n-modules.txt" cat /proc/modules
    capture "$n-drm-nodes.txt" ls -l /dev/dri
    capture "$n-processes.txt" ps -A
    capture "$n-process-labels.txt" ps -AZ
    capture "$n-top.txt" top -b -n 1 -m 20
    capture "$n-cpu-pressure.txt" sh -c 'cat /proc/stat /proc/loadavg /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io'
    if [ "$n" = 10 ]; then
        capture "$n-kernel-final.txt" sh -c 'dmesg | tail -c 1048576'
    else
        capture "$n-kernel-errors.txt" sh -c 'dmesg | grep -E "avc:|[Ee]rror|[Ff]ail|[Tt]imeout|[Hh]ang|iwlwifi|Bluetooth" | tail -c 262144'
    fi
    capture "$n-radio-display-state.txt" sh -c 'cat /sys/module/firmware_class/parameters/path /sys/module/drm/parameters/debug; ip link; for key in vendor.hwc.drm.force_color_mode vendor.hwc.drm.persistent_hdr vendor.hwc.drm.enable_color_pipeline vendor.hwc.use_log_gamma_lut qemu.sf.lcd_density; do echo "$key=$(getprop "$key")"; done'
    capture "$n-wifi.txt" dumpsys -t 5 wifi
    capture "$n-cpuinfo.txt" dumpsys -t 5 cpuinfo
    capture "$n-display-latency.txt" dumpsys -t 5 SurfaceFlinger --latency
    capture "$n-services.txt" service list
    capture "$n-memory.txt" cat /proc/meminfo
    capture "$n-selinux.txt" getenforce
    for service in activity window display power SurfaceFlinger; do
        capture "$n-dumpsys-$service.txt" dumpsys -t 5 "$service"
    done
    if [ "$n" = 01 ] || [ "$n" = 10 ]; then
        # AVF/Linux terminal evidence only: do not start VMs or change settings.
        capture "$n-virtualization-hardware.txt" sh -c 'ls -l /dev/kvm /dev/vhost-vsock /dev/vsock; grep -E "^(flags|vendor_id|model name)" /proc/cpuinfo | head -n 3; cat /sys/module/kvm_intel/parameters/nested /sys/module/kvm/parameters/enable_virt_at_load'
        capture "$n-virtualization-state.txt" sh -c 'getprop | grep -Ei "virtual|hypervisor|avf|ferro|linux|terminal"; ps -AZ | grep -Ei "virtual|crosvm|virtmgr|terminal|vm_shell"; cat /proc/mounts | grep -E "com.android.virt|/data/misc/apexdata"; ls -ldZ /apex/com.android.virt /data/misc/apexdata/com.android.virt'
        capture "$n-virtualization-packages.txt" sh -c 'pm list packages -f | grep -Ei "terminal|virtual|ferro|linux"'
        capture "$n-virtualization-service.txt" dumpsys -t 5 android.system.virtualizationservice
        capture "$n-virtualization-info.txt" /apex/com.android.virt/bin/vm info
        capture "$n-terminal-package.txt" dumpsys -t 5 package com.android.virtualization.terminal
        capture "$n-virtualization-logcat.txt" sh -c 'logcat -b all -d -v threadtime | grep -Ei "virtualizationservice|VirtualMachine|crosvm|AVF|ferrochrome|debian|VmLauncher|LinuxTerminal|VmTerminalApp|DebianService|virtmgr|vmnic|kvm|pvmfw" | tail -c 524288'
        capture "$n-dumpsys-package.txt" dumpsys -t 5 package
        for package in com.android.settings com.google.android.desktop.setupwizard com.google.android.gms com.google.android.apps.nexuslauncher; do
            capture "$n-gfxinfo-$package.txt" dumpsys -t 5 gfxinfo "$package" framestats
        done
    fi
    if ! kill -0 "$live" 2>/dev/null; then
        wait "$live"
        echo "LIVE_LOGCAT_EXIT=$? $(date)" >> "$status"
        # Its error is preserved in logger-stderr; a new file preserves old data.
        logcat -b all -v threadtime -f "$run/live-logcat-restart-$n.txt" -r 2048 -n 1 &
        live=$!
    fi
    sync
    sleep 20
done
capture final-logcat.txt logcat -b all -d -v threadtime
echo "LOGGER_COMPLETE $(date)" >> "$status"
sync
