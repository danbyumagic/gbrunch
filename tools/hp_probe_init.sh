#!/bin/sh
export PATH=/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /dev
mount -t tmpfs tmpfs /run
mount -t tmpfs tmpfs /tmp
mknod /dev/console c 5 1
mknod /dev/null c 1 3
mknod /dev/kmsg c 1 11
mdev -s
mkdir -p /dev/pts /probe /logs /run/report
mount -t devpts devpts /dev/pts
MODE=$(cat /etc/gbrunch-mode)
RUN=$(date -u +%Y%m%d-%H%M%S)-$MODE
REPORT=/run/report
mkfifo /run/probe-output
if [ -c /dev/ttyS0 ]; then
 tee "$REPORT/probe-stdout.txt" /dev/console /dev/ttyS0 < /run/probe-output &
else
 tee "$REPORT/probe-stdout.txt" /dev/console < /run/probe-output &
fi
exec > /run/probe-output 2>&1
printf '\nGBRUNCH_HP_DIAGNOSTICS_STARTED mode=%s\n' "$MODE"
echo 'Only the uniquely marked test-drive FAT partition may receive logs.'
echo 'No HP internal filesystem is mounted. No firmware updater or Android service is started.'
# Capture a useful inventory even when peripheral driver loading fails.
load_modules() {
 if [ "$MODE" = linux ]; then
  while read filename; do
   echo "GBRUNCH_MATCHING_MODULE $filename"
   insmod "/lib/modules/$(uname -r)/$filename" || echo "GBRUNCH_MODULE_UNAVAILABLE_OR_LOAD_FAILED $filename"
  done < /etc/module-load-order
 else
  if [ -f /etc/xe-load-order ]; then
   while read filename; do
    insmod "/xe/$filename"
    rc=$?
    echo "GBRUNCH_XE_MODULE_RESULT $filename status=$rc"
    echo "GBRUNCH_XE_MODULE_RESULT $filename status=$rc" > /dev/kmsg
   done < /etc/xe-load-order
  fi
  for mod in virtio_pci_modern_dev virtio_pci_legacy_dev virtio_pci virtio_blk; do
   echo "GBRUNCH_ORIGINAL_SIGNED_MODULE $mod"
   insmod /modules/$mod.ko || echo "GBRUNCH_MODULE_LOAD_FAILED $mod"
  done
 fi
}
load_modules > "$REPORT/module-load.txt" 2>&1
cat "$REPORT/module-load.txt"
sleep 3
mdev -s
# Select exactly one partition by GPT disk+partition GUID/CRC, FAT serial and marker.
CANDIDATES=0
MEDIUM=
PARENT=
for p in /sys/class/block/*; do
 [ -f "$p/partition" ] || continue
 name=${p##*/}
 parent=$(basename "$(dirname "$(readlink -f "$p")")")
 [ -b "/dev/$name" ] && [ -b "/dev/$parent" ] || continue
 if hp-media-id "/dev/$name" "/dev/$parent" >> "$REPORT/media-selection.txt" 2>&1; then
  if mount -t vfat -o ro,nosuid,nodev,noexec "/dev/$name" /probe; then
   if [ "$(cat /probe/GBRUNCH-MEDIA.TXT 2>/dev/null)" = 'GBRUNCH-HP-DIAGNOSTICS-v1-4b475242-4750-4812-9e53-f143c82f517a' ]; then
    CANDIDATES=$((CANDIDATES+1)); MEDIUM="/dev/$name"; PARENT="/dev/$parent"
   fi
   umount /probe
  fi
 fi
done
if [ "$CANDIDATES" != 1 ]; then
 echo "GBRUNCH_LOG_STORAGE_REFUSED matching_media=$CANDIDATES"
 MEDIUM=; PARENT=
else
 echo "GBRUNCH_LOG_TARGET $MEDIUM parent=$PARENT"
fi
# Write-protect all other block devices for this diagnostic boot only.
for p in /sys/class/block/*; do
 name=${p##*/}; dev="/dev/$name"
 [ -b "$dev" ] || continue
 [ "$dev" = "$MEDIUM" ] || [ "$dev" = "$PARENT" ] || blockdev --setro "$dev"
done
section() { printf '\n===== %s =====\n' "$1"; }
{
 section 'Boot and CPU'; uname -a; cat /proc/version /proc/cmdline /proc/cpuinfo
 section 'DMI model and BIOS (serial/UUID omitted)'
 for f in sys_vendor product_name product_version board_vendor board_name board_version bios_vendor bios_version bios_date chassis_type; do
  printf '%s: ' "$f"; cat "/sys/class/dmi/id/$f" 2>/dev/null
 done
 section 'PCI vendor/device/subsystem IDs, modalias and binding'
 for d in /sys/bus/pci/devices/*; do
  echo "DEVICE $d"
  for f in vendor device subsystem_vendor subsystem_device class revision irq modalias current_link_speed current_link_width max_link_speed max_link_width; do
   [ -f "$d/$f" ] && { printf '%s: ' "$f"; cat "$d/$f"; }
  done
  printf 'driver: '; readlink "$d/driver" || echo unbound
 done
 section 'USB devices'
 for d in /sys/bus/usb/devices/*; do
  [ -f "$d/idVendor" ] || continue
  echo "DEVICE $d"
  for f in idVendor idProduct bcdDevice bDeviceClass product manufacturer speed; do
   [ -f "$d/$f" ] && { printf '%s: ' "$f"; cat "$d/$f"; }
  done
  readlink "$d/driver"
 done
 section 'I2C, SPI and platform modalias/bindings'
 for bus in i2c spi platform; do
  for d in /sys/bus/$bus/devices/*; do
   [ -d "$d" ] || continue
   echo "DEVICE $d"; cat "$d/name" "$d/modalias" 2>/dev/null; readlink "$d/driver"
  done
 done
 section 'ACPI IDs and paths'
 for d in /sys/bus/acpi/devices/*; do
  echo "DEVICE $d"; cat "$d/hid" "$d/uid" "$d/path" "$d/status" "$d/modalias" 2>/dev/null
 done
 section 'Input devices'; cat /proc/bus/input/devices
 section 'Block inventory and read-only flags'
 for d in /sys/class/block/*; do
  echo "DEVICE $d"; readlink -f "$d"
  for f in size ro removable queue/logical_block_size queue/physical_block_size device/model; do
   [ -f "$d/$f" ] && { printf '%s: ' "$f"; cat "$d/$f"; }
  done
 done
 section 'Network bindings (no network configured)'
 for d in /sys/class/net/*; do echo "$d"; readlink -f "$d/device/driver"; cat "$d/operstate" 2>/dev/null; done
 section 'Power, tablet and sensors'
 for d in /sys/class/power_supply/*; do echo "$d"; cat "$d/type" "$d/status" "$d/capacity" 2>/dev/null; done
 for d in /sys/bus/iio/devices/*; do echo "$d"; cat "$d/name" 2>/dev/null; done
 ls -l /sys/bus/thunderbolt/devices /sys/class/drm /sys/class/video4linux /sys/class/sound 2>/dev/null
 section 'Display/framebuffer'; cat /proc/fb; ls -l /dev/fb* /dev/dri/* 2>/dev/null
 section 'DRM connectors and modes'
 for d in /sys/class/drm/*; do
  echo "DEVICE $d"; readlink -f "$d/device/driver"
  for f in status enabled modes dpms; do
   [ -f "$d/$f" ] && { echo "$f:"; cat "$d/$f"; }
  done
 done
 section 'Loaded modules'; cat /proc/modules
 section 'Mounted filesystems'; cat /proc/mounts
} > "$REPORT/hardware.txt" 2>&1
# Persist a checkpoint before GPU execution/modesetting, in case either hangs.
save_graphics_checkpoint() {
 [ -n "$MEDIUM" ] || return
 dmesg > "$REPORT/kernel-dmesg.txt"
 if mount -t vfat -o rw,nosuid,nodev,noexec,utf8 "$MEDIUM" /logs; then
  mkdir -p "/logs/GBRUNCH-LOGS/$RUN"
  cp -R "$REPORT/." "/logs/GBRUNCH-LOGS/$RUN/"
  echo "$1" > "/logs/GBRUNCH-LOGS/$RUN/GRAPHICS-STAGE.txt"
  sync; umount /logs
 fi
}
case " $(cat /proc/cmdline) " in
 *' gbrunch.graphics=1 '*)
  save_graphics_checkpoint before-xe-render
  timeout 20 hp-xe-graphics render /dev/dri/renderD128 > "$REPORT/xe-render.txt" 2>&1
  echo "helper_status=$?" >> "$REPORT/xe-render.txt"
  cat "$REPORT/xe-render.txt"
  save_graphics_checkpoint before-display-modeset
  timeout 30 hp-xe-graphics display /dev/dri/card0 > "$REPORT/xe-display.txt" 2>&1
  echo "helper_status=$?" >> "$REPORT/xe-display.txt"
  cat "$REPORT/xe-display.txt"
  save_graphics_checkpoint after-graphics-checks
 ;;
esac
# Read-only ACPI table copies support later HP audio/hinge/ISH investigation.
mkdir "$REPORT/acpi"
for f in /sys/firmware/acpi/tables/DSDT /sys/firmware/acpi/tables/SSDT*; do
 [ -f "$f" ] && cp "$f" "$REPORT/acpi/"
done
dmesg > "$REPORT/kernel-dmesg.txt"
cat "$REPORT/hardware.txt"
printf 'mode=%s\nrun=%s\nlog_target=%s\nother_block_devices=read-only\n' "$MODE" "$RUN" "$MEDIUM" > "$REPORT/status.txt"
SAVED=0
if [ -n "$MEDIUM" ]; then
 if mount -t vfat -o rw,nosuid,nodev,noexec,utf8 "$MEDIUM" /logs; then
  mkdir -p "/logs/GBRUNCH-LOGS/$RUN"
  if cp -R "$REPORT/." "/logs/GBRUNCH-LOGS/$RUN/"; then
   printf 'GBRUNCH_HP_DIAGNOSTICS_COMPLETE mode=%s\n' "$MODE" > "/logs/GBRUNCH-LOGS/$RUN/COMPLETE.txt"
   sync
   SAVED=1
   echo "GBRUNCH_LOGS_SAVED /GBRUNCH-LOGS/$RUN"
  fi
  umount /logs
 fi
fi
echo "GBRUNCH_HP_DIAGNOSTICS_COMPLETE mode=$MODE saved=$SAVED"
echo "GBRUNCH_HP_DIAGNOSTICS_COMPLETE mode=$MODE saved=$SAVED" > /dev/kmsg
case " $(cat /proc/cmdline) " in
 *' gbrunch.batch=1 '*)
 if [ "$MODE" = linux ]; then
  export REPORT MEDIUM RUN
  hp-batch-tests > "$REPORT/batch-tests.txt" 2>&1
  echo "GBRUNCH_BATCH_RESULT status=$?"
  # Load the original Google diagnostic kernel/initrd from the uniquely identified medium.
  # kexec keeps this independent of HP's permanent/one-shot UEFI boot order.
  if [ "$SAVED" = 1 ] && mount -t vfat -o ro,nosuid,nodev,noexec "$MEDIUM" /logs; then
   kexec -l /logs/EFI/GBRUNCH/google-kernel --initrd=/logs/EFI/GBRUNCH/google-initrd.gz --append="$(cat /etc/google-cmdline)" > "$REPORT/kexec.txt" 2>&1
   rc=$?;umount /logs
   if mount -t vfat -o rw,nosuid,nodev,noexec,utf8 "$MEDIUM" /logs; then
    cp -R "$REPORT/." "/logs/GBRUNCH-LOGS/$RUN/"
    echo "load_status=$rc" >> "/logs/GBRUNCH-LOGS/$RUN/kexec.txt"
    sync;umount /logs
   fi
   if [ "$rc" = 0 ]; then
    echo 'Linux batch saved. Starting the original Google kernel automatically; screen may stop updating.'
    sync;kexec -e
    echo 'kexec execution failed; select Google kernel manually from the same USB menu.'
   else echo 'kexec loading unavailable; select Google kernel manually from the same USB menu.';fi
  else echo 'No verified log medium: refusing automatic kernel transition.';fi
 fi
 ;;
esac
case " $(cat /proc/cmdline) " in
 *' gbrunch.autopoweroff=1 '*) sleep 2; poweroff -f ;;
esac
if [ "$MODE" = google ]; then
 echo 'Original Googlebook kernel has no built-in graphical text console. Powering off in 15 seconds.'
 sleep 15
 poweroff -f
fi
echo 'Diagnostics complete. Logs are on the test drive in GBRUNCH-LOGS.'
echo 'Type poweroff -f to shut down, or reboot -f to reboot.'
# Keep a visible console on the fallback Linux kernel.
exec setsid sh -c 'exec sh </dev/console >/dev/console 2>&1'
