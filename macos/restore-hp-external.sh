#!/usr/bin/env bash
# Download source, build locally from Google, then confirm and flash an external SSD.
set -euo pipefail
[[ $(uname -s) == Darwin ]] || { echo 'Run this script on macOS.' >&2; exit 1; }
[[ $EUID -ne 0 ]] || { echo 'Run without sudo; only the final disk write requests sudo.' >&2; exit 1; }
export PATH="/opt/homebrew/opt/e2fsprogs/sbin:/usr/local/opt/e2fsprogs/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"
for cmd in python3 qemu-system-x86_64 qemu-img qemu-io mcopy mformat lz4 mke2fs e2fsck; do
 if ! command -v "$cmd" >/dev/null; then echo 'First install the build tools: brew install python qemu mtools lz4 e2fsprogs' >&2; exit 1; fi
done
work=${GBRUNCH_EXTERNAL_WORK:-"$HOME/gbrunch-hp-external"}
stage=$(mktemp -d /tmp/gbrunch-mac-source.XXXXXX)
trap 'rm -rf "$stage"' EXIT
curl -fL --retry 2 https://github.com/danbyumagic/gbrunch/archive/refs/heads/experiment/single-partition.zip -o "$stage/source.zip"
/usr/bin/ditto -x -k "$stage/source.zip" "$stage/repo"
repo="$stage/repo/gbrunch-experiment-single-partition"
[[ -f "$repo/tools/build_hp_external_wsl.sh" ]] || { echo 'Unexpected source archive layout.' >&2; exit 1; }
image="$work/gbrunch-hp-external-r4.img.gz"
if [[ ! -f "$image" || ! -f "$image.sha256" ]]; then
 GBRUNCH_EXTERNAL_WORK="$work" bash "$repo/tools/build_hp_external_wsl.sh"
fi
/usr/sbin/diskutil list external physical
printf '\nEnter the external SSD whole disk, e.g. /dev/disk21 (not a partition): '
read -r target
python3 "$repo/macos/flash_external_ssd.py" --image "$image" --disk "$target"
