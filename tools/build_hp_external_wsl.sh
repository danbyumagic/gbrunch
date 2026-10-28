#!/usr/bin/env bash
# Build only: never opens a Windows physical drive or changes boot configuration.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=${GBRUNCH_EXTERNAL_WORK:-"$HOME/gbrunch-hp-external"}
if [[ "$work" == *" "* || "$work" == *","* ]]; then echo "Choose a work path without spaces or commas for QEMU." >&2; exit 1; fi
if [[ -e "$work" ]]; then echo "Work directory already exists: $work. Preserve it; choose a fresh GBRUNCH_EXTERNAL_WORK." >&2; exit 1; fi
for cmd in python3 qemu-system-x86_64 qemu-img qemu-io mcopy mformat lz4 mke2fs e2fsck gzip; do
 if ! command -v "$cmd" >/dev/null; then
  echo 'Missing build dependencies. In your existing Ubuntu WSL, run:' >&2
  echo 'sudo apt update && sudo apt install -y python3 qemu-system-x86 qemu-utils mtools lz4 e2fsprogs gzip ca-certificates' >&2
  exit 1
 fi
done
free=$(python3 -c 'import pathlib,shutil; print(shutil.disk_usage(pathlib.Path.home()).free)')
if (( free < 45000000000 )); then echo 'At least 45 GB free is required for the local sparse build/cache and compressed result.' >&2; exit 1; fi
mkdir -p "$work/source" "$work/cache"
cp -a "$repo/tools" "$repo/profiles" "$work/source/"
exec > >(tee "$work/build.log") 2>&1
echo "Building private HP external image in $work. No SSD writes will be made."
python3 "$work/source/tools/fetch_toolbox_assets.py"
python3 "$work/source/tools/assemble_native_android.py" --download \
 --recovery-profile "$work/source/profiles/ruby-16658739.json" \
 --assets "$work/source/assets" --cache "$work/cache" \
 --output "$work/native-r4.qcow2" --format qcow2
python3 "$work/source/tools/add_external_userdata.py" --source "$work/native-r4.qcow2" --output "$work/hp-external.qcow2" --userdata-gib 16
qemu-img convert -f qcow2 -O raw -S 64k "$work/hp-external.qcow2" "$work/gbrunch-hp-external-r4.img"
gzip -1 -c "$work/gbrunch-hp-external-r4.img" > "$work/gbrunch-hp-external-r4.img.gz.partial"
mv "$work/gbrunch-hp-external-r4.img.gz.partial" "$work/gbrunch-hp-external-r4.img.gz"
(cd "$work" && sha256sum gbrunch-hp-external-r4.img.gz > gbrunch-hp-external-r4.img.gz.sha256)
echo 'Build complete. Google-derived files stay private; do not upload them.'
echo "Image: $work/gbrunch-hp-external-r4.img.gz"
echo 'This uses the traditional multi-partition HP layout, original Google kernel and V7 compatibility.'
echo 'R4 is newer than the physically tested HP recovery. A successful build is not proof of HP boot.'
echo 'The image is not written to an SSD. Keep the cache/QCOW2 backing files together.'
if [[ $(uname -s) == Darwin ]]; then echo "Open the build directory with: open \"$work\""; else echo 'Open this WSL directory in Windows Explorer with: explorer.exe .'; fi
