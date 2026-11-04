#!/bin/bash
# Build the Googlebook disk image for the profile in this release kit, from Google's official recovery.
# The kit (tools/usb/package-release.sh output) holds only open-source and redistributable files; this
# script downloads the recovery (or takes a local recovery.zip), checks its hash, and runs the kit's
# assemble_native_android.py, which derives the kernel, ramdisk and GBVENDOR locally in a QEMU build VM.
# Runs as a normal user on x86_64 Linux. Needs about 50 GB free in OUTDIR.
# OUTDIR/usb-kit/ is then copied to a data USB stick for the steps in usb-kit/README.txt.
# Usage: bash make-usb-kit.sh [--recovery-zip recovery.zip] OUTDIR
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
zip=
[ "${1:-}" = --recovery-zip ] && { zip=$(realpath "${2:?recovery.zip}"); shift 2; }
out=${1:?usage: bash make-usb-kit.sh [--recovery-zip recovery.zip] OUTDIR}
assets=$(ls -d "$here"/assets-* 2>/dev/null | head -n1)
[ -n "$assets" ] && [ -f "$here/SHA256SUMS" ] || { echo "Run this from an unpacked release kit (assets-*/ and SHA256SUMS not found)"; exit 1; }

missing=
for t in python3 qemu-system-x86_64 qemu-img qemu-io mcopy mformat lz4 sha256sum; do command -v "$t" >/dev/null || missing="$missing $t"; done
if [ -n "$missing" ]; then
	echo "Missing programs:$missing"
	echo "Ubuntu/Debian: sudo apt install python3 qemu-system-x86 qemu-utils mtools lz4"
	exit 1
fi

echo "Checking the kit files..."
(cd "$here" && sha256sum -c --quiet SHA256SUMS) || { echo "Kit files do not match SHA256SUMS; download the kit again"; exit 1; }

mkdir -p "$out"; out=$(realpath "$out")
kit=$out/usb-kit; img=$kit/googlebook-dragonfly.img
[ ! -e "$img" ] || { echo "$img already exists; remove it or use another OUTDIR"; exit 1; }
need=$((50*1024*1024))  # KiB; recovery zip 7.8 GB + raw 19 GB (sparse) + image 19 GB
[ -n "$zip" ] && need=$((42*1024*1024))
[ -f "$out/recovery-cache/ruby-recovery.raw" ] && need=$((22*1024*1024))  # rebuild: image only
free=$(df -Pk "$out" | awk 'NR==2{print $4}')
[ "$free" -ge "$need" ] || { echo "Not enough space in $out: $((free/1024/1024)) GiB free, about $((need/1024/1024)) GiB needed"; exit 1; }

mkdir -p "$kit"
src=(--download); [ -n "$zip" ] && src=(--recovery-zip "$zip")
echo "Building the image (downloads 7.8 GB unless --recovery-zip is given)..."
python3 "$assets/assemble_native_android.py" "${src[@]}" --cache "$out/recovery-cache" \
	--assets "$assets" --format raw --output "$img"
mv "$img.build-vm.log" "$out/" 2>/dev/null || true
mv "$img.manifest.json" "$out/" 2>/dev/null || true

echo "Writing the image hash..."
(cd "$kit" && sha256sum googlebook-dragonfly.img > googlebook-dragonfly.img.sha256)
mkdir -p "$kit/usb"
cp "$here"/usb/*.sh "$kit/usb/"
cp "$here/README-usb-kit.txt" "$kit/README.txt"
echo
echo "Done: $kit"
echo "Copy that folder to a data USB stick formatted as exFAT or ext4 (the image is larger than 4 GB),"
echo "then follow $kit/README.txt."
echo "The downloaded recovery stays in $out/recovery-cache for a later rebuild; delete it to free about 27 GB."
echo "The image contains Google's recovery: do not share it."
