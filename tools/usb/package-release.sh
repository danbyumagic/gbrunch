#!/bin/bash
# Package a redistributable release kit from a profile asset directory (tools/prepare_profile_assets.py
# output). The kit holds the assets, the USB scripts, make-usb-kit.sh and license notices; users build
# the disk image from Google's recovery with make-usb-kit.sh. The asset directory is checked against its
# native-assets.json and the profile's pinned compat.ext4, so no locally derived vendor, kernel or image
# can enter the kit. The tarball is reproducible (sorted names, fixed mtime and owner, gzip -n).
# Usage: bash package-release.sh assets-dir OUTDIR
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); repo=$(cd "$here/../.." && pwd)
assets=$(realpath "${1:?usage: bash package-release.sh assets-dir OUTDIR}"); outdir=${2:?OUTDIR}
prof=$(ls "$assets"/profile-*.json 2>/dev/null | head -n1)
[ -n "$prof" ] || { echo "$assets has no profile-*.json (not a prepare_profile_assets.py output)"; exit 1; }
profile=$(basename "$prof" .json); profile=${profile#profile-}

python3 -I - "$assets" "$profile" "$repo/tools" <<'EOF'
import hashlib,json,pathlib,sys
assets=pathlib.Path(sys.argv[1]);sys.path.insert(0,sys.argv[3])
import prepare_profile_assets as p
def sha(f):
    h=hashlib.sha256()
    with open(f,'rb') as r:
        for b in iter(lambda:r.read(1<<20),b''):h.update(b)
    return h.hexdigest()
files=json.loads((assets/'native-assets.json').read_text())['files']
on_disk={str(f.relative_to(assets)) for f in assets.rglob('*') if f.is_file()}-{'native-assets.json'}
if on_disk!=set(files):sys.exit('Files differ from native-assets.json: %s'%sorted(on_disk^set(files)))
for n,h in files.items():
    if sha(assets/n)!=h:sys.exit('Asset hash mismatch: '+n)
want=p.PROFILES[sys.argv[2]]['compat_sha256']
if files['compat.ext4']!=want:sys.exit('compat.ext4 %s is not the pinned %s image %s'%(files['compat.ext4'],sys.argv[2],want))
EOF

compat=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["files"]["compat.ext4"][:8])' "$assets/native-assets.json")
name=gbrunch-$profile-kit-$compat
mkdir -p "$outdir"; outdir=$(realpath "$outdir")
stage=$outdir/$name; tarball=$outdir/$name.tar.gz
[ ! -e "$stage" ] && [ ! -e "$tarball" ] || { echo "$stage or $tarball exists"; exit 1; }
mkdir "$stage"
cp -r "$assets" "$stage/assets-$profile"
mkdir "$stage/usb" "$stage/licenses" "$stage/licenses/camera"
cp "$here"/grow-userdata.sh "$here"/reset-firstboot.sh "$here"/apply-profile-update.sh "$here"/apply-vendor-update.sh "$stage/usb/"
cp "$here/make-usb-kit.sh" "$here/kit/README.txt" "$here/kit/README-usb-kit.txt" "$here/kit/NOTICE.txt" "$stage/"
cp "$here/kit/GPL-2.0.txt" "$repo/LICENSE" "$stage/licenses/"
cp "$repo"/camera/licenses/* "$stage/licenses/camera/"
chmod -R u+rwX,go+rX,go-w "$stage"
(cd "$stage" && find . -type f ! -name SHA256SUMS | sed 's|^\./||' | LC_ALL=C sort | xargs sha256sum > SHA256SUMS)
tar -C "$outdir" --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -cf - "$name" | gzip -n -9 > "$tarball"
(cd "$outdir" && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")
rm -rf "$stage"
echo "Release kit: $tarball ($(du -h "$tarball" | cut -f1))"
cat "$tarball.sha256"
