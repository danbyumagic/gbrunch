#!/bin/bash
# Replace the GBVENDOR partition of an existing Googlebook USB disk with a newly built vendor.erofs.
# Usage: sudo bash apply-vendor-update.sh /dev/sdX vendor.erofs
set -euo pipefail
d=${1:?usage: sudo bash apply-vendor-update.sh /dev/sdX vendor.erofs}; v=${2:?vendor.erofs}
[ "$(lsblk -dno TRAN "$d")" = usb ] || { echo "$d is not a USB disk"; exit 1; }
[ -z "$(lsblk -no MOUNTPOINTS "$d" | tr -d '[:space:]')" ] || { echo "Unmount all partitions of $d first"; exit 1; }
p=$(lsblk -lnpo NAME,PARTLABEL "$d" | awk '$2=="GBVENDOR"{print $1}')
[ "$(echo "$p" | wc -w)" = 1 ] || { echo "need exactly one GBVENDOR partition on $d"; exit 1; }
[ "$(head -c 1028 "$v" | tail -c 4 | od -An -tx1 | tr -d ' ')" = e2e1f5e0 ] || { echo "$v is not an EROFS image"; exit 1; }
size=$(stat -c %s "$v"); part=$(blockdev --getsize64 "$p")
[ "$size" -le "$part" ] || { echo "vendor image ($size) larger than GBVENDOR ($part)"; exit 1; }
want=$(sha256sum "$v" | cut -c1-64)
echo "GBVENDOR=$p image=$v ($size of $part bytes)"
dd if="$v" of="$p" bs=1M conv=fsync status=none
[ "$(head -c "$size" "$p" | sha256sum | cut -c1-64)" = "$want" ] || { echo "GBVENDOR readback mismatch"; exit 1; }
sync; echo "done: GBVENDOR replaced ($want)"
