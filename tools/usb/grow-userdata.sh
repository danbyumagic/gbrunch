#!/bin/bash
# Move Android userdata of a freshly written raw image (assemble_native_android.py --format raw) to the
# free tail of the USB disk. The image's userdata is 4 GiB and unformatted; first boot then fills it
# (ENOSPC, system_server restart loop). The old partition is kept as userdata_small so only one
# partition is named userdata, and the new one is formatted as the trial does.
# Usage: sudo bash grow-userdata.sh /dev/sdX
set -euo pipefail
d=${1:?usage: sudo bash grow-userdata.sh /dev/sdX}
[ "$(lsblk -dno TRAN "$d")" = usb ] || { echo "$d is not a USB disk"; exit 1; }
name() { lsblk -no PARTLABEL "${d}$1" 2>/dev/null; }
[ "$(name 1)" = userdata ] && [ "$(name 33)" = GBLOG ] && [ -z "$(name 34)" ] || { echo "$d is not a fresh Googlebook image (sdX1=userdata, sdX33=GBLOG, no sdX34 expected)"; exit 1; }
[ -z "$(lsblk -no MOUNTPOINTS "$d" | tr -d '[:space:]')" ] || { echo "Unmount all partitions of $d first"; exit 1; }
sgdisk -e "$d"                                   # backup GPT header to the real disk end
sgdisk -c 1:userdata_small "$d"                  # keep the old 4 GiB partition, but unnamed for Android
sgdisk -n 34:0:0 -t 34:8300 -c 34:userdata "$d"  # new userdata in all remaining space
partprobe "$d"; udevadm settle
p=${d}34
[ "$(lsblk -no PARTLABEL "$p")" = userdata ] || { echo "new partition not found"; exit 1; }
mke2fs -F -t ext4 -b 4096 -I 512 -i 16384 -m 0 \
  -O none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity \
  -E encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard -J size=64 -M /data "$p"
sync
lsblk -o NAME,SIZE,FSTYPE,PARTLABEL "$d" | grep -E "userdata|NAME"
