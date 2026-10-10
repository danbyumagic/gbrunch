#!/bin/sh
export PATH=/bin:/usr/bin
export PYTHONHOME=/usr
export PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /run
mount -t tmpfs tmpfs /tmp
[ -d /sys/firmware/efi ] && mkdir -p /sys/firmware/efi/efivars
while read m; do insmod /modules/$m 2>/dev/null || true; done < /etc/module-order
insmod /modules/loop.ko 2>/dev/null || true
while read m; do insmod /installer-modules/$m 2>/dev/null || true; done < /etc/installer-module-order
mount -t efivarfs efivarfs /sys/firmware/efi/efivars 2>/dev/null || true
mdev -s
if grep -q 'gbrunch.prepare_usb=1' /proc/cmdline; then
 if mount -t vfat /dev/vdb /work; then
  python3 /installer/prepare_standalone_guest.py > /work/prepare-log.txt 2>&1
  cat /work/prepare-log.txt; sync; umount /work
 fi
 poweroff -f
fi
if grep -q 'gbrunch.fixture_tests=1' /proc/cmdline; then
 if mount -t ext4 /dev/vda /work; then
  python3 /installer/test_installer_guest.py > /work/guest-tests.txt 2>&1
  rc=$?; cat /work/guest-tests.txt; echo "INSTALLER_FIXTURE_TEST_EXIT=$rc"
  sync; umount /work
 fi
 poweroff -f
fi
if grep -q 'gbrunch.installed_probe=1' /proc/cmdline; then
 python3 /installer/test_installed_layout.py
 sync; poweroff -f
fi
# Persistent logs live only on the marked installer USB, never on Windows.
i=0
while [ "$i" -lt 15 ]; do
 mdev -s
 logdev=$(blkid -L GBINSTALL 2>/dev/null)
 if [ -n "$logdev" ] && mount -t vfat -o nosuid,nodev,noexec "$logdev" /logs; then
  if [ "$(cat /logs/GBRUNCH-INSTALLER.txt 2>/dev/null)" = 'GBRUNCH Linux dualboot installer v1' ]; then break; fi
  umount /logs
 fi
 i=$((i+1)); sleep 1
done
if [ "$i" -ge 15 ]; then
 echo 'Installer log USB not found. Installation is disabled. Power off and retry.' > /dev/console
 while :; do sleep 60; done
fi
# Persistent kernel evidence for storage/USB/firmware failures.
dmesg > /logs/kernel-boot.txt
cat /proc/cmdline > /logs/installer-cmdline.txt
# Interactive UI uses the physical screen/keyboard. Serial remains diagnostic.
exec </dev/tty1 >/dev/tty1 2>&1
if blkid -L GBPAYLOAD >/dev/null 2>&1; then
 set -o pipefail
 python3 /installer/standalone_bootstrap.py 2>&1 | tee /logs/standalone-bootstrap.txt
 rc=$?; set +o pipefail
 if [ "$rc" -ne 0 ]; then
  echo 'Payload verification failed. Installation disabled. Logs preserved.'
  read answer; sync; umount /logs; poweroff -f
 fi
fi
python3 /installer/installer_console.py
sync
umount /logs
poweroff -f
