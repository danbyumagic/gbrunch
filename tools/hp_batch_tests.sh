#!/bin/sh
# Additional driver/behavior tests. No internal filesystem mounts or updates.
export PATH=/bin
echo 'GBRUNCH_FULL_BATCH_STARTED'
SUMMARY="$REPORT/test-summary.txt"
say() { echo "$*"; echo "$*" > /dev/console; [ ! -c /dev/ttyS0 ] || echo "$*" > /dev/ttyS0; }
checkpoint() {
 dmesg > "$REPORT/kernel-dmesg.txt"
 if [ -n "$MEDIUM" ] && mount -t vfat -o rw,nosuid,nodev,noexec,utf8 "$MEDIUM" /logs; then
  mkdir -p "/logs/GBRUNCH-LOGS/$RUN"
  cp -R "$REPORT/." "/logs/GBRUNCH-LOGS/$RUN/"
  sync; umount /logs
 fi
}
say 'Full batch: collecting CPU, driver, graphics, audio, radio, camera and sensor evidence.'
echo 'Test labels distinguish PASS/FAIL/SKIP/OBSERVE. Linux driver success is not Android HAL success.' > "$SUMMARY"
ulimit -c 0
for test in gfni vnni; do
 case "$test" in gfni) flags='gfni vpclmulqdq avx2';expected=fac410b5009f4d4f;; vnni) flags='avx_vnni avx2';expected=cd09a9370c7cef79;; esac
 supported=1
 for flag in $flags; do grep -qw "$flag" /proc/cpuinfo || supported=0; done
 if [ "$supported" = 1 ]; then
  timeout 8 "/bin/hp-cpu-$test" > "$REPORT/cpu-$test.txt" 2>&1
  if [ "$?" = 0 ] && grep -q "$expected" "$REPORT/cpu-$test.txt"; then
   echo "PASS CPU $test actual instructions and expected digest" >> "$SUMMARY"
  else echo "FAIL CPU $test execution/digest; inspect cpu-$test.txt" >> "$SUMMARY"; fi
 else echo "SKIP CPU $test: required features not advertised ($flags); Googlebook compatibility unresolved" >> "$SUMMARY"; fi
done
say 'Loading matching Linux peripheral drivers. Screen may flicker when Intel graphics starts.'
checkpoint
while read filename; do
 echo "DRIVER_BEGIN $filename"
 case "$filename" in i915.ko) checkpoint;; esac
 # Run asynchronously so a blocked kernel probe cannot hold the entire batch.
 insmod "/lib/modules/$(uname -r)/$filename" > "$REPORT/driver-$filename.txt" 2>&1 &
 pid=$!;seconds=0
 while kill -0 "$pid" 2>/dev/null && [ "$seconds" -lt 100 ]; do sleep 0.1;seconds=$((seconds+1)); done
 if kill -0 "$pid" 2>/dev/null; then
  kill -TERM "$pid" 2>/dev/null
  echo "OBSERVE module $filename: probe exceeded 10s, remaining tests continue" >> "$SUMMARY"
 else
  wait "$pid";rc=$?
  echo "OBSERVE module $filename: insmod status=$rc (loaded does not prove device binding)" >> "$SUMMARY"
 fi
done < /etc/extra-module-load-order
sleep 3;mdev -s
mkdir -p /sys/kernel/debug
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null
{
 echo 'Post-driver PCI/USB bindings'
 for d in /sys/bus/pci/devices/* /sys/bus/usb/devices/*; do
  [ -L "$d/driver" ] && { echo "$d"; readlink "$d/driver"; }
 done
 echo 'Loaded modules';cat /proc/modules
 echo 'Sound cards, PCM devices and codecs';cat /proc/asound/cards /proc/asound/pcm
 for f in /proc/asound/card*/codec*; do [ ! -f "$f" ] || cat "$f"; done
 echo 'ALSA playback enumeration';aplay -l
 echo 'ALSA capture enumeration';aplay -l -C
 echo 'Bluetooth controllers';ls -l /sys/class/bluetooth
 for d in /sys/class/bluetooth/*; do [ ! -e "$d" ] || { readlink -f "$d"; cat "$d/address" "$d/name" 2>/dev/null; };done
 echo 'Radio blocks';for d in /sys/class/rfkill/*; do cat "$d/name" "$d/type" "$d/soft" "$d/hard" 2>/dev/null;done
 echo 'TPM binding/status only; no provisioning or clearing';ls -l /sys/class/tpm
 echo 'Thunderbolt/USB4 topology; no device authorization changes';ls -lR /sys/bus/thunderbolt/devices
 echo 'Suspend modes and wakeup sources';cat /sys/power/state /sys/power/mem_sleep /sys/kernel/debug/wakeup_sources
} > "$REPORT/peripheral-bindings.txt" 2>&1
{
 echo 'DRM connectors, status, modes and EDID (no resolution changes)'
 for d in /sys/class/drm/*; do
  [ -d "$d" ] || continue;echo "$d";readlink -f "$d/device/driver"
  for f in status enabled modes dpms; do [ ! -f "$d/$f" ] || { echo "$f";cat "$d/$f"; };done
  if [ -s "$d/edid" ]; then echo 'EDID';od -Ax -tx1 "$d/edid";fi
 done
 for f in /sys/kernel/debug/dri/*/i915_capabilities /sys/kernel/debug/dri/*/i915_engine_info /sys/kernel/debug/dri/*/i915_display_info /sys/kernel/debug/dri/*/i915_guc_info; do
  [ ! -f "$f" ] || { echo "$f";cat "$f"; }
 done
} > "$REPORT/graphics.txt" 2>&1
for node in /dev/dri/renderD*; do
 [ -c "$node" ] || continue
 timeout 12 hp-device-probe gpu "$node" >> "$REPORT/graphics.txt" 2>&1
 echo "OBSERVE GPU command-submission $node status=$?; inspect graphics.txt" >> "$SUMMARY"
done
for node in /dev/nvme[0-9]; do
 [ -c "$node" ] || continue
 timeout 6 hp-device-probe nvme "$node" > "$REPORT/nvme-${node##*/}-health.txt" 2>&1
 echo "OBSERVE read-only NVMe SMART $node status=$?" >> "$SUMMARY"
done
if [ -n "$MEDIUM" ]; then
 timeout 12 hp-device-probe storage "$MEDIUM" > "$REPORT/usb-storage-read.txt" 2>&1
 echo "OBSERVE external storage read sample status=$?" >> "$SUMMARY"
fi
echo 'OBSERVE graphics: see driver bindings, connector modes and firmware errors; no accelerated Android compositor test' >> "$SUMMARY"
{
 echo 'IIO sensor names and raw channels'
 for d in /sys/bus/iio/devices/iio:device*; do
  [ -d "$d" ] || continue;echo "$d";cat "$d/name"
  for f in "$d"/*_raw "$d"/*_scale; do [ ! -f "$f" ] || { echo "$f";cat "$f"; };done
 done
} > "$REPORT/sensors.txt" 2>&1
iw dev > "$REPORT/wifi.txt" 2>&1
for d in /sys/class/net/*; do
 [ -d "$d/phy80211" ] || continue;iface=${d##*/}
 echo "INTERFACE $iface" >> "$REPORT/wifi.txt"
 ip link set "$iface" up >> "$REPORT/wifi.txt" 2>&1
 # Filter scan output: no SSIDs/BSS MAC addresses or network credentials stored.
 timeout 18 iw dev "$iface" scan > /run/wifi-scan.txt 2>&1;rc=$?
 awk '/freq:|signal:|command failed|Network is down|Operation not|No such/{print}' /run/wifi-scan.txt >> "$REPORT/wifi.txt"
 echo "scan_status=$rc" >> "$REPORT/wifi.txt"
 if [ "$rc" = 0 ]; then echo "PASS Wi-Fi scan $iface (association/internet not tested)" >> "$SUMMARY";else echo "FAIL/SKIP Wi-Fi scan $iface status=$rc; inspect wifi.txt and radio blocks" >> "$SUMMARY";fi
 ip link set "$iface" down
 rm -f /run/wifi-scan.txt
done
say 'Testing webcam frame delivery briefly. No images or video are saved.'
for camera in /dev/video*; do
 [ -c "$camera" ] || continue
 timeout 12 hp-camera-probe "$camera" > "$REPORT/camera-${camera##*/}.txt" 2>&1;rc=$?
 echo "OBSERVE camera $camera status=$rc; capability/frame counts in its report" >> "$SUMMARY"
done
say 'Input check: move/click the touchpad, touch the screen, press volume keys and rotate/fold the laptop for 40 seconds.'
seconds=40
case " $(cat /proc/cmdline) " in *' gbrunch.unattended=1 '*) seconds=2;; esac
(
 for sample in $(seq 1 "$seconds"); do
  echo "SAMPLE $sample"
  for f in /sys/bus/iio/devices/iio:device*/*_raw; do [ ! -f "$f" ] || { echo "$f";cat "$f"; };done
  sleep 1
 done
) > "$REPORT/sensor-motion.txt" 2>&1 &
sensor_pid=$!
hp-input-probe "$seconds" > "$REPORT/input-events.txt" 2>&1
kill -TERM "$sensor_pid" 2>/dev/null
echo 'OBSERVE input/switch activity: see input-events.txt; no activity means inconclusive, not device failure' >> "$SUMMARY"
echo 'SKIP automatic audio playback/recording: enumeration and SOF/codec firmware/bindings collected; audible output requires user confirmation' >> "$SUMMARY"
echo 'SKIP Bluetooth pairing and USB4 external-device transfers: controller/binding evidence collected, accessory needed' >> "$SUMMARY"
case " $(cat /proc/cmdline) " in
 *' gbrunch.unattended=1 '*) echo 'SKIP guided audio/suspend: unattended test fixture' >> "$SUMMARY";;
 *)
 say 'Optional audible speaker check: press a within 15 seconds. Otherwise this is skipped.'
 if read -t 15 -n 1 answer < /dev/console && [ "$answer" = a ]; then
  card=$(awk '/^[ ]*[0-9]+ \[/{n=$1} /sof-hda-dsp|sofhdadsp/{print n;exit}' /proc/asound/cards)
  if [ -n "$card" ]; then
   say 'Playing left/right test audio briefly. Note whether you hear both speakers.'
   timeout 12 speaker-test -D "plughw:$card,0" -c 2 -t wav -l 1 > "$REPORT/speaker-test.txt" 2>&1
   echo "OBSERVE speaker-test status=$?; report audible result separately" >> "$SUMMARY"
  else echo 'SKIP audible test: SOF HDA speaker card not identified; inspect ALSA enumeration' >> "$SUMMARY";fi
 fi
 say 'Optional suspend/resume check: press s within 15 seconds. Expected wake is 20 seconds; power button if stuck after 60.'
 if read -t 15 -n 1 answer < /dev/console && [ "$answer" = s ]; then
  echo 'SUSPEND_TEST_START; check this record if the laptop does not resume' >> "$SUMMARY";checkpoint
  hp-suspend-test > "$REPORT/suspend-test.txt" 2>&1;rc=$?
  echo "OBSERVE suspend test returned status=$rc; inspect PM messages and verify screen/input after resume" >> "$SUMMARY"
  hp-input-probe 10 > "$REPORT/input-after-suspend.txt" 2>&1
 else echo 'SKIP suspend/resume: user did not select optional test' >> "$SUMMARY";fi
 ;;
esac
cat "$SUMMARY"
checkpoint
echo 'GBRUNCH_FULL_BATCH_COMPLETE'
