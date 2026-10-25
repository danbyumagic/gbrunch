#!/bin/busybox sh
export PATH=/bin
/bin/busybox --install -s /bin
mkdir -p /proc /sys /dev /host /system-test /data-test
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
exec >/dev/console 2>&1
fail() { echo "CONTAINER_FAIL:$*"; sync; poweroff -f; while :; do sleep 1; done; }
# Modules are supplied by the caller from the exact kernel build, in dependency order.
while read module; do insmod "/modules/$module" || fail "module:$module"; done < /modules/order
mdev -s
count=0
while [ ! -b /dev/vda1 ]; do
 sleep 1; mdev -s; count=$((count+1)); [ "$count" -lt 15 ] || fail host_partition_missing
done
# Refuse a volume that needs recovery; never run fsck or format anything here.
mount -t ext4 -o rw,noload /dev/vda1 /host || fail host_mount
[ "$(cat /host/CONTAINER-TEST.txt)" = 'GBRUNCH FILE-ONLY FIXTURE' ] || fail host_identity
[ -f /host/googlebook.img ] || fail image_missing
losetup -P /dev/loop0 /host/googlebook.img || fail loop_attach
mdev -s
[ -b /dev/loop0p1 ] && [ -b /dev/loop0p2 ] || fail nested_partitions
mount -t ext4 -o ro,noload /dev/loop0p1 /system-test || fail system_mount
[ "$(cat /system-test/marker)" = 'GOOGLEBOOK_SYSTEM_FIXTURE' ] || fail system_marker
mount -t ext4 -o rw,noload /dev/loop0p2 /data-test || fail data_mount
n=$(cat /data-test/boots 2>/dev/null || echo 0)
n=$((n+1)); echo "$n" > /data-test/boots
sync
echo "CONTAINER_PASS:system_ro:data_rw:boots=$n"
cat /proc/partitions
umount /data-test || fail data_unmount
umount /system-test || fail system_unmount
losetup -d /dev/loop0 || fail loop_detach
umount /host || fail host_unmount
sync
poweroff -f
while :; do sleep 1; done
