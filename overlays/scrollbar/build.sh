#!/bin/bash
# Build GbrunchScrollbarOverlay.apk, the static RRO that widens Android's View scrollbars (10dp).
#
#   overlays/scrollbar/build.sh WORK FRAMEWORK_RES_APK [OUTDIR]
#
# WORK gets the pinned Android build-tools (aapt2/zipalign/apksigner, ~60 MB download) and the public
# AOSP test signing key; both are verified by sha256. FRAMEWORK_RES_APK is framework-res.apk from the
# local recovery (system_a/system/framework/framework-res.apk after tools/prepare_recovery.py): aapt2
# needs it to resolve the android: attributes of the manifest, and nothing of it is copied into the
# output. OUTDIR defaults to profiles/hp-dragonfly-g4/vendor/overlay. The build is reproducible: the
# same inputs give a byte-identical APK (aapt2 zeroes zip timestamps; RSA PKCS#1 signatures are
# deterministic), so the sha256 is recorded in tools/prepare_profile_assets.py.
#
# Needs: curl, unzip, java (apksigner), sha256sum.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
work=$(realpath -m "${1:?WORK dir}"); fwres=$(realpath "${2:?framework-res.apk}")
out=$(realpath -m "${3:-$here/../../profiles/hp-dragonfly-g4/vendor/overlay}")

BT_URL=https://dl.google.com/android/repository/build-tools_r36_linux.zip
BT_SHA=5d9ac77fb6ff43d9da518a337b4fcf8f9097113df531d99ccefe80ef7ce8250b
KEY_URL='https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security'
PK8_SHA=495675d32e89a149d5abe191f4e9c0e218b9068714e9b53a7c91e164a0741a23
PEM_SHA=a4384ba815b9499a5ce349b4e33c1755278873fe2eac150a068823f526e6dbde

fetch() {	# fetch URL DEST SHA256 [base64]
	if [ ! -e "$2" ] || ! echo "$3  $2" | sha256sum -c --quiet - 2>/dev/null; then
		echo "Downloading $1" >&2
		if [ "${4:-}" = base64 ]; then curl -sfL "$1" | base64 -d > "$2.tmp"; else curl -sfL -o "$2.tmp" "$1"; fi
		echo "$3  $2.tmp" | sha256sum -c --quiet -
		mv "$2.tmp" "$2"
	fi
}

mkdir -p "$work/dl" "$out"
fetch "$BT_URL" "$work/dl/build-tools_r36_linux.zip" "$BT_SHA"
fetch "$KEY_URL/testkey.pk8?format=TEXT" "$work/dl/testkey.pk8" "$PK8_SHA" base64
fetch "$KEY_URL/testkey.x509.pem?format=TEXT" "$work/dl/testkey.x509.pem" "$PEM_SHA" base64
bt="$work/build-tools/android-16"
if [ ! -x "$bt/aapt2" ]; then
	rm -rf "$work/build-tools"; mkdir -p "$work/build-tools"
	unzip -q "$work/dl/build-tools_r36_linux.zip" -d "$work/build-tools"
fi

tmp=$(mktemp -d "$work/build.XXXXXX"); trap 'rm -rf "$tmp"' EXIT
"$bt/aapt2" compile --dir "$here/res" -o "$tmp/res.zip"
# --no-resource-removal: keep every overlaid resource even though nothing in this package references it.
"$bt/aapt2" link --no-resource-removal --manifest "$here/AndroidManifest.xml" -I "$fwres" \
	--min-sdk-version 37 --target-sdk-version 37 -o "$tmp/unsigned.apk" "$tmp/res.zip"
"$bt/zipalign" -f 4 "$tmp/unsigned.apk" "$tmp/aligned.apk"
"$bt/apksigner" sign --key "$work/dl/testkey.pk8" --cert "$work/dl/testkey.x509.pem" --v4-signing-enabled false \
	--out "$out/GbrunchScrollbarOverlay.apk" "$tmp/aligned.apk"
"$bt/aapt2" dump resources "$out/GbrunchScrollbarOverlay.apk" | grep -q 'config_scrollbarSize' || { echo "resource missing" >&2; exit 1; }
sha256sum "$out/GbrunchScrollbarOverlay.apk"
