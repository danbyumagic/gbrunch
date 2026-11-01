#!/bin/bash
# Return a Googlebook USB disk to a clean first boot: restore metadata and misc from the raw image it
# was written from (clears RescueParty/boot-loop counters and any pending recovery command) and
# reformat userdata. GBLOG is kept.
# Usage: sudo bash reset-firstboot.sh /dev/sdX image.img
set -euo pipefail
d=${1:?usage: sudo bash reset-firstboot.sh /dev/sdX image.img}; img=${2:?image.img}
[ "$(lsblk -dno TRAN "$d")" = usb ] || { echo "$d is not a USB disk"; exit 1; }
[ -z "$(lsblk -no MOUNTPOINTS "$d" | tr -d '[:space:]')" ] || { echo "Unmount all partitions of $d first"; exit 1; }
part() { local p; p=$(lsblk -lnpo NAME,PARTLABEL "$d" | awk -v n="$1" '$2==n{print $1}'); [ "$(echo "$p" | wc -w)" = 1 ] || { echo "need exactly one '$1' partition on $d"; exit 1; }; echo "$p"; }
meta=$(part metadata); misc=$(part misc); data=$(part userdata); part GBLOG >/dev/null
# "start size" in bytes of a named partition in the image's GPT
span() { sfdisk -J "$img" | python3 -c "
import json,sys
t=json.load(sys.stdin)['partitiontable'];s=t.get('sectorsize',512)
p=[p for p in t['partitions'] if p.get('name')==sys.argv[1]]
if len(p)!=1:sys.exit('image: need exactly one %s partition'%sys.argv[1])
print(p[0]['start']*s,p[0]['size']*s)" "$1"; }
restore() {  # restore partition $2 from the image partition named $1, after checking the sizes match
  local s n; read -r s n < <(span "$1")
  [ "$(blockdev --getsize64 "$2")" = "$n" ] || { echo "$1: size differs between $d and $img"; exit 1; }
  dd if="$img" of="$2" bs=1M iflag=skip_bytes,count_bytes skip="$s" count="$n" conv=fsync status=none
}
echo "metadata=$meta misc=$misc userdata=$data image=$img"
restore metadata "$meta"; restore misc "$misc"
mke2fs -q -F -t ext4 -b 4096 -I 512 -i 16384 -m 0 \
  -O none,has_journal,ext_attr,dir_index,filetype,extent,casefold,sparse_super,large_file,huge_file,uninit_bg,dir_nlink,extra_isize,quota,project,verity \
  -E encoding=utf8-12.1,lazy_itable_init=0,lazy_journal_init=0,nodiscard -J size=64 -M /data "$data"
sync
echo "done: clean first boot prepared ($(lsblk -no SIZE "$data") userdata)"
