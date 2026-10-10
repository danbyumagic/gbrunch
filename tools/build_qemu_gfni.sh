#!/usr/bin/env bash
# Build the experimental host-side emulator; never edits Google guest images.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$root/tools/python/bin:$root/tools/local/usr/bin:$PATH"
export PYTHONPATH="$root/tools/python${PYTHONPATH:+:$PYTHONPATH}"
export PKG_CONFIG_LIBDIR="$root/tools/local/usr/lib/x86_64-linux-gnu/pkgconfig:$root/tools/local/usr/share/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$root/tools/local"
source_dir="$root/sources/qemu11"
commit=4fc49f46dc95d4a27de2509e7fceb2931e91faeb
if [ ! -d "$source_dir/.git" ]; then
  git clone --depth 1 --branch v11.1.2 https://gitlab.com/qemu-project/qemu.git "$source_dir"
fi
[ "$(git -C "$source_dir" rev-parse HEAD)" = "$commit" ]
if git -C "$source_dir" apply --check "$root/patches/qemu11-gfni.patch" 2>/dev/null; then
  git -C "$source_dir" apply "$root/patches/qemu11-gfni.patch"
else
  git -C "$source_dir" apply --reverse --check "$root/patches/qemu11-gfni.patch"
fi
mkdir -p "$root/build/qemu11"
cd "$root/build/qemu11"
if [ ! -f build.ninja ]; then
  "$source_dir/configure" --target-list=x86_64-softmmu,x86_64-linux-user \
    --without-default-features --enable-tcg --enable-tools --disable-docs --disable-rust --disable-werror
fi
ninja -j3 qemu-system-x86_64 qemu-x86_64 qemu-img qemu-io
cd "$root"
gcc -O2 -static -o build/gfni-test tools/test_gfni.c
build/gfni-test > evidence/gfni-native.txt
build/qemu11/qemu-x86_64 -cpu max build/gfni-test > evidence/gfni-emulated.txt
diff -u evidence/gfni-native.txt evidence/gfni-emulated.txt

# Optional native VNNI oracle needs AVX512-VNNI+VL on the host.
gcc -O2 -static -o build/vnni-native tools/test_vnni.c
gcc -O2 -static -DEMULATED_AVX -o build/vnni-emulated tools/test_vnni.c
build/vnni-native > evidence/vnni-native.txt
build/qemu11/qemu-x86_64 -cpu max build/vnni-emulated > evidence/vnni-emulated.txt
diff -u evidence/vnni-native.txt evidence/vnni-emulated.txt
