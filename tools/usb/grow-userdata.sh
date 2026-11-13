#!/bin/bash
# Move Android userdata of a freshly written raw image (assemble_native_android.py --format raw) to the
# free tail of the disk. The image's userdata is 4 GiB and unformatted; first boot then fills it
# (ENOSPC, system_server restart loop). The old partition is kept as userdata_small so only one
# partition is named userdata, and the new one is formatted as the trial does.
# USB disks only, unless --internal is given (an internal disk the image was written to).
# Usage: sudo bash grow-userdata.sh [--internal] /dev/sdX|/dev/nvmeXnY
set -euo pipefail
internal=0; [ "${1:-}" = --internal ] && { internal=1; shift; }
d=${1:?usage: sudo bash grow-userdata.sh [--internal] /dev/sdX|/dev/nvmeXnY}
[ "$(lsblk -dno TYPE "$d")" = disk ] || { echo "$d is not a whole disk"; exit 1; }
tran=$(lsblk -dno TRAN "$d")
if [ "$internal" = 1 ]; then [ "$tran" != usb ] || { echo "$d is a USB disk; drop --internal"; exit 1; }
else [ "$tran" = usb ] || { echo "$d is not a USB disk (use --internal for an internal disk)"; exit 1; }; fi
[ "$(blockdev --getss "$d")" = 512 ] || { echo "$d does not use 512-byte sectors"; exit 1; }
num() { lsblk -lnpo NAME,PARTN,PARTLABEL "$d" | awk -v n="$1" '$2==n{print $3}'; }      # label of partition n
path() { lsblk -lnpo NAME,PARTN "$d" | awk -v n="$1" '$2==n{print $1}'; }               # device of partition n
[ "$(num 1)" = userdata ] && [ "$(num 33)" = GBLOG ] && [ -z "$(path 34)" ] || { echo "$d is not a fresh Googlebook image (partition 1=userdata, 33=GBLOG, no 34 expected)"; exit 1; }
[ -z "$(lsblk -no MOUNTPOINTS "$d" | tr -d '[:space:]')" ] || { echo "Unmount all partitions of $d first"; exit 1; }
sgdisk -e "$d"                                   # backup GPT header to the real disk end
sgdisk -c 1:userdata_small "$d"                  # keep the old 4 GiB partition, but unnamed for Android
sgdisk -n 34:0:0 -t 34:8300 -c 34:userdata "$d"  # new userdata in all remaining space
partprobe "$d"; udevadm settle
p=$(path 34)
[ -n "$p" ] && [ "$(lsblk -no PARTLABEL "$p")" = userdata ] || { echo "new partition not found"; exit 1; }
mke2fs -F -t ext4 -b 4096 -I 512 -i 16384 -m 0 \
  -O none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity \
  -E encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard -J size=64 -M /data "$p"
sync
lsblk -o NAME,SIZE,FSTYPE,PARTLABEL "$d" | grep -E "userdata|NAME"
