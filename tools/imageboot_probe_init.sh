#!/imageboot/busybox sh
export PATH=/imageboot:/imageboot/applets
B=/imageboot/busybox
$B mkdir -p /imageboot/applets /proc /sys /dev /host /inner /run
$B --install -s /imageboot/applets
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /dev
mknod /dev/console c 5 1
mknod /dev/null c 1 3
mknod /dev/fuse c 10 229
mknod /dev/loop-control c 10 237
mknod /dev/loop0 b 7 0
exec >/dev/console 2>&1
fail() { cat /proc/partitions; ls -l /dev; echo "IMAGEBOOT_FAIL:$*"; sync; poweroff -f; while :; do sleep 1; done; }
echo IMAGEBOOT_KERNEL_STARTED
# Modules are the matching originals in the locally assembled Android ramdisk.
while read module; do insmod /lib/modules/$module || echo "IMAGEBOOT_MODULE:$module"; done < /lib/modules/modules.load
mdev -s
i=0
hostdev=''
while [ -z "$hostdev" ]; do
 mdev -s
 for candidate in /dev/sd[a-z] /dev/nvme*n*p*; do
  [ -b "$candidate" ] || continue
  blkid "$candidate" | grep -q 'LABEL="GBRUNCH_TEST_HOST"' && hostdev="$candidate" && break
 done
 [ -n "$hostdev" ] && break
 sleep 1; i=$((i+1)); [ "$i" -lt 15 ] || fail disk_missing
done
# norecover refuses unsafe/unclean volumes; never remove a Windows hibernation file.
ntfs-3g -o rw,norecover "$hostdev" /host || fail ntfs_mount
[ -f /host/gbrunch.img ] || fail image_missing
losetup -P /dev/loop0 /host/gbrunch.img || fail loop_setup
mdev -s
cat /proc/partitions
mount -t ext4 /dev/loop0p1 /inner || fail nested_mount
[ "$(cat /inner/marker.txt)" = GBRUNCH_NESTED_IMAGE_OK ] || fail marker
count=$(cat /inner/boot-count.txt 2>/dev/null || echo 0)
count=$((count+1))
echo "$count" > /inner/boot-count.txt
sync
echo "IMAGEBOOT_PASS:NTFS_LOOP_GPT_EXT4_RW:boot_count=$count"
umount /inner || fail nested_unmount
losetup -d /dev/loop0 || fail detach
umount /host || fail ntfs_unmount
sync
poweroff -f
while :; do sleep 1; done
