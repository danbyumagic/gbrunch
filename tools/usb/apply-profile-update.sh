#!/bin/bash
# Update an existing Googlebook USB disk in place from a regenerated profile asset directory
# (tools/prepare_profile_assets.py output): replace the GBRUNCH (/oem) partition with its
# compat.ext4 and set the profile's kernel options (profile-*.json cmdline_append) in
# EFI/GBRUNCH/grub.cfg. System, vendor, userdata and GBLOG are not touched.
# USB disks only, unless --internal is given (an internal disk the image was written to).
# Usage: sudo bash apply-profile-update.sh [--internal] /dev/sdX|/dev/nvmeXnY assets-dir
set -euo pipefail
internal=0; [ "${1:-}" = --internal ] && { internal=1; shift; }
d=${1:?usage: sudo bash apply-profile-update.sh [--internal] /dev/sdX|/dev/nvmeXnY assets-dir}; assets=${2:?assets-dir}
[ "$(lsblk -dno TYPE "$d")" = disk ] || { echo "$d is not a whole disk"; exit 1; }
tran=$(lsblk -dno TRAN "$d")
if [ "$internal" = 1 ]; then [ "$tran" != usb ] || { echo "$d is a USB disk; drop --internal"; exit 1; }
else [ "$tran" = usb ] || { echo "$d is not a USB disk (use --internal for an internal disk)"; exit 1; }; fi
[ -z "$(lsblk -no MOUNTPOINTS "$d" | tr -d '[:space:]')" ] || { echo "Unmount all partitions of $d first"; exit 1; }
part() { local p; p=$(lsblk -lnpo NAME,PARTLABEL "$d" | awk -v n="$1" '$2==n{print $1}'); [ "$(echo "$p" | wc -w)" = 1 ] || { echo "need exactly one '$1' partition on $d"; exit 1; }; echo "$p"; }
gb=$(part GBRUNCH); esp=$(part EFI-SYSTEM); part GBLOG >/dev/null
compat="$assets/compat.ext4"
want=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['files']['compat.ext4'])" "$assets/native-assets.json")
[ "$(sha256sum "$compat" | cut -c1-64)" = "$want" ] || { echo "compat.ext4 does not match native-assets.json"; exit 1; }
[ "$(blockdev --getsize64 "$gb")" = "$(stat -c %s "$compat")" ] || { echo "GBRUNCH size differs from compat.ext4"; exit 1; }
records=("$assets"/profile-*.json)
[ "${#records[@]}" = 1 ] && [ -f "${records[0]}" ] || { echo "need exactly one profile-*.json in $assets"; exit 1; }
extra=$(python3 -c "
import json,re,sys
x=json.load(open(sys.argv[1])).get('cmdline_append','')
if not re.fullmatch(r'[A-Za-z0-9_.=, -]*',x):sys.exit('unsafe cmdline_append')
print(x)" "${records[0]}")
echo "GBRUNCH=$gb EFI=$esp options: $extra"
dd if="$compat" of="$gb" bs=1M conv=fsync status=none
[ "$(head -c 67108864 "$gb" | sha256sum | cut -c1-64)" = "$want" ] || { echo "GBRUNCH readback mismatch"; exit 1; }
mnt=$(mktemp -d); trap 'umount "$mnt" 2>/dev/null; rmdir "$mnt"' EXIT
mount "$esp" "$mnt"; cfg="$mnt/EFI/GBRUNCH/grub.cfg"
[ -f "$cfg.before-profile-update" ] || cp "$cfg" "$cfg.before-profile-update"
for o in $extra; do  # replace an existing value of the same option, else insert before init_rc
  if grep -q " ${o%%=*}=" "$cfg"; then sed -i "s/ ${o%%=*}=[^ ]*/ $o/g" "$cfg"
  else sed -i "s| androidboot.init_rc=| $o androidboot.init_rc=|" "$cfg"; fi
done
if command -v grub-script-check >/dev/null; then grub-script-check "$cfg"; fi
for o in $extra; do grep -q " $o " "$cfg" || { echo "option $o missing from grub.cfg"; exit 1; }; done
sync; echo "done: GBRUNCH replaced and kernel options applied"
