#!/bin/bash
# Build the GBRUNCH internal-camera stack (HP Dragonfly G4 hi556 / IPU6) for Android x86_64.
#
#   camera/build.sh WORK          WORK: an empty or previous work directory (about 3 GB)
#
# Downloads (all pinned and verified): Android NDK r30, upstream libcamera at df8e348d (v0.8.0) plus
# camera/patches/0001-gbrunch-android.patch, libyuv at the libcamera wrap revision, libjpeg-turbo 3.2.1,
# libexif 0.6.26, and meson/ninja into a Python venv. libexif is compiled directly with a hand-written
# config.h (no configure script is run). Output: WORK/out, the --camera directory of
# tools/prepare_profile_assets.py:
#   out/lib64/   bind-mounted over /vendor/lib64/libcamera: libcamera{,-base,-hal}.so, libc++_shared.so,
#                libcamera/ipa/ipa_softisp.so, share/libcamera/ipa/softisp/*.yaml, etc/libcamera/camera_hal.yaml
#   out/bin/gbcam-probe              manual capture test (logcat tag gbcam)
#   out/vendor/camera.gbrunch.so     GBVENDOR /vendor/lib64/hw module that loads lib64/libcamera-hal.so
# The output is byte-reproducible, independent of the WORK path and the build date (checked with two WORK
# directories); it prints the sha256 of every file.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mkdir -p "${1:?usage: camera/build.sh WORK}" && cd "$1" && pwd)
D=$W/downloads; mkdir -p "$D"

NDK_URL=https://dl.google.com/android/repository/android-ndk-r30-linux.zip
NDK_SHA256=753611f410d002cfcd3f3dc2ef49aad532089d3180b436c060a90bf0fcb64df2
LIBCAMERA_URL=https://git.libcamera.org/libcamera/libcamera.git
LIBCAMERA_COMMIT=df8e348d64b4932a0676256ed24f0da3ee9438bc
JPEG_URL=https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.2.1/libjpeg-turbo-3.2.1.tar.gz
JPEG_SHA256=c27ad72a68da151177929aa969ae773a2da5ac2af9ce946079314fdac8cece7f
EXIF_URL=https://github.com/libexif/libexif/releases/download/v0.6.26/libexif-0.6.26.tar.xz
EXIF_SHA256=4a055ed6575e61ca46c3172be3c753cc16c9becd0f99ec71d58dd0e471476c0c

fetch() {  # url sha256
	local f=$D/$(basename "$1")
	if [ ! -f "$f" ]; then
		curl -fL --retry 3 -o "$f.part" "$1"
		mv "$f.part" "$f"
	fi
	echo "$2  $f" | sha256sum -c --quiet
}

# Tools and sources
[ -x "$W/venv/bin/meson" ] || { python3 -m venv "$W/venv"; "$W/venv/bin/pip" -q install meson==1.12.1 ninja==1.13.2 jinja2 pyyaml ply; }
export PATH=$W/venv/bin:$PATH
fetch $NDK_URL $NDK_SHA256
[ -d "$W/android-ndk-r30" ] || unzip -q "$D/android-ndk-r30-linux.zip" -d "$W"
N=$W/android-ndk-r30/toolchains/llvm/prebuilt/linux-x86_64
if [ ! -d "$W/libcamera" ]; then
	git clone -q "$LIBCAMERA_URL" "$W/libcamera"
	git -C "$W/libcamera" checkout -q "$LIBCAMERA_COMMIT"
	git -C "$W/libcamera" apply "$HERE/patches/0001-gbrunch-android.patch"
	echo "0.8.0+gbrunch-${LIBCAMERA_COMMIT:0:8}" > "$W/libcamera/.tarball-version"  # no build-time date
	# meson reports failure for libyuv (a cmake subproject, no meson.build); check the result instead.
	(cd "$W/libcamera" && meson subprojects download libyuv libyaml >/dev/null || true)
	[ -f "$W/libcamera/subprojects/libyuv/CMakeLists.txt" ] && [ -d "$W/libcamera/subprojects/yaml-0.2.5" ]
fi
fetch $JPEG_URL $JPEG_SHA256
fetch $EXIF_URL $EXIF_SHA256

# Static dependencies in WORK/deps
P=$W/deps; mkdir -p "$P/lib/pkgconfig" "$P/include" "$P/stub" "$W/deps-build"
TC=(-DCMAKE_TOOLCHAIN_FILE=$W/android-ndk-r30/build/cmake/android.toolchain.cmake -DANDROID_ABI=x86_64
    -DANDROID_PLATFORM=android-35 -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    -G Ninja -DCMAKE_MAKE_PROGRAM=$W/venv/bin/ninja)
if [ ! -f "$P/lib/libjpeg.a" ]; then
	rm -rf "$W/deps-build/libjpeg-turbo-3.2.1"; tar xzf "$D/libjpeg-turbo-3.2.1.tar.gz" -C "$W/deps-build"
	cmake -S "$W/deps-build/libjpeg-turbo-3.2.1" -B "$W/deps-build/libjpeg-turbo-3.2.1/build" "${TC[@]}" \
		-DENABLE_SHARED=OFF -DENABLE_STATIC=ON -DWITH_TURBOJPEG=OFF -DWITH_TOOLS=OFF -DWITH_TESTS=OFF \
		-DWITH_SIMD=OFF -DBUILD=gbrunch -DCMAKE_INSTALL_PREFIX="$P" -DCMAKE_INSTALL_LIBDIR=lib >/dev/null  # no build date
	ninja -C "$W/deps-build/libjpeg-turbo-3.2.1/build" install >/dev/null
fi
if [ ! -f "$P/lib/libexif.a" ]; then
	E=$W/deps-build/libexif-0.6.26; rm -rf "$E"; tar xJf "$D/libexif-0.6.26.tar.xz" -C "$W/deps-build"
	cp "$HERE/src/libexif-config.h" "$E/config.h"; mkdir -p "$E/obj" "$P/include/libexif"
	for c in "$E"/libexif/*.c "$E"/libexif/*/*.c; do
		o=$E/obj/$(echo "${c#$E/libexif/}" | tr / _).o
		"$N/bin/x86_64-linux-android35-clang" -O2 -fPIC -w -I"$E" -I"$E/libexif" -c "$c" -o "$o"
	done
	"$N/bin/llvm-ar" rcsD "$P/lib/libexif.a" "$E"/obj/*.o
	cp "$E"/libexif/exif-*.h "$E/libexif/exif.h" "$E/libexif/_stdint.h" "$P/include/libexif/"
fi
if [ ! -f "$P/lib/libyuv.a" ]; then
	cmake -S "$W/libcamera/subprojects/libyuv" -B "$W/deps-build/libyuv" "${TC[@]}" -DCMAKE_PREFIX_PATH="$P" \
		-DJPEG_INCLUDE_DIR="$P/include" -DJPEG_LIBRARY="$P/lib/libjpeg.a" -DBUILD_TESTING=OFF >/dev/null
	ninja -C "$W/deps-build/libyuv" yuv >/dev/null
	cp "$W/deps-build/libyuv/libyuv.a" "$P/lib/"
	cp -r "$W/libcamera/subprojects/libyuv/include/libyuv" "$W/libcamera/subprojects/libyuv/include/libyuv.h" "$P/include/"
fi
# Link-time stubs: the device's libhardware.so and LLNDK libcamera_metadata.so are used at run time.
printf 'struct hw_module_t;\nint hw_get_module(const char *id, const struct hw_module_t **module) { (void)id; *module = 0; return -1; }\n' > "$P/stub/libhardware_stub.c"
"$N/bin/x86_64-linux-android35-clang" -shared -fPIC -Wl,-soname,libhardware.so "$P/stub/libhardware_stub.c" -o "$P/stub/libhardware.so"
I=$W/libcamera/include/android
"$N/bin/x86_64-linux-android35-clang" -shared -fPIC -O2 -w -I"$I/metadata" -I"$I/system/core/include" \
	-I"$W/libcamera/src/android/metadata" -Wl,-soname,libcamera_metadata.so \
	"$W/libcamera/src/android/metadata/camera_metadata.c" -llog -o "$P/stub/libcamera_metadata.so"
pc() { printf 'prefix=%s\nName: %s\nDescription: GBRUNCH static or stub build\nVersion: %s\nLibs: %s\nCflags: %s\n' "$P" "$1" "$2" "$3" "$4" > "$P/lib/pkgconfig/$1.pc"; }
pc libexif 0.6.26 '-L${prefix}/lib -lexif -lm' '-I${prefix}/include'
pc libyuv 0 '-L${prefix}/lib -lyuv -ljpeg' '-I${prefix}/include -DHAVE_JPEG'
# The stub directory goes in the cross file's link args: a -L in pkg-config would leave its absolute path
# in the binaries as a build rpath string.
pc libhardware 1 '-lhardware' ''
pc libcamera_metadata 1 '-lcamera_metadata' ''

# libcamera (simple pipeline, software ISP, Android HAL) with prefix /vendor, libdir lib64/libcamera
cat > "$W/android-hal.ini" <<EOF
[binaries]
c = '$N/bin/x86_64-linux-android35-clang'
cpp = '$N/bin/x86_64-linux-android35-clang++'
ar = '$N/bin/llvm-ar'
strip = '$N/bin/llvm-strip'
pkg-config = 'pkg-config'
cmake = '$(command -v cmake)'

[built-in options]
c_args = ['-march=x86-64-v3']
cpp_args = ['-march=x86-64-v3', '-DGBRUNCH_TRUST_IPA']
c_link_args = ['-Wl,-rpath,/vendor/lib64/libcamera', '-L$P/stub']
cpp_link_args = ['-Wl,-rpath,/vendor/lib64/libcamera', '-L$P/stub']

[host_machine]
system = 'android'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'

[properties]
pkg_config_libdir = ['$P/lib/pkgconfig']
EOF
B=$W/build-hal
[ -d "$B" ] || meson setup "$B" "$W/libcamera" --cross-file "$W/android-hal.ini" \
	--prefix=/vendor --libdir=lib64/libcamera --sysconfdir=lib64/libcamera/etc --datadir=lib64/libcamera/share \
	--libexecdir=lib64/libcamera/libexec -Dpipelines=simple -Dipas=softisp -Dandroid=enabled \
	-Dandroid_platform=generic -Dcam=disabled -Dqcam=disabled -Dgstreamer=disabled -Dtest=false \
	-Ddocumentation=disabled -Dudev=disabled -Dv4l2=false -Dlc-compliance=disabled -Dpycamera=disabled \
	-Dtracing=disabled -Dlibdw=disabled -Dlibunwind=disabled -Dsoftisp-gpu=disabled -Dbuildtype=release >/dev/null
ninja -C "$B" >/dev/null
rm -rf "$W/stage" "$W/out"; DESTDIR=$W/stage ninja -C "$B" install >/dev/null
S=$W/stage/vendor/lib64/libcamera
mkdir -p "$W/obj"; cp "$HERE/src/gbcam_probe.cpp" "$HERE/src/camera_gbrunch_trampoline.c" "$W/obj/"
cd "$W"  # relative include paths: header paths end up in assertion strings
"$N/bin/x86_64-linux-android35-clang++" -std=c++20 -O2 -march=x86-64-v3 -Wall -I stage/vendor/include/libcamera \
	obj/gbcam_probe.cpp -L "$S" -lcamera -lcamera-base -llog \
	-Wl,-rpath,/vendor/lib64/libcamera:/oem/camera/lib64 -o "$W/obj/gbcam-probe"
"$N/bin/x86_64-linux-android35-clang" -O2 -fPIC -shared -Wall -Werror -I "$I/hardware/libhardware/include" \
	-I "$I/system/core/include" -I "$I/metadata" obj/camera_gbrunch_trampoline.c -ldl -llog \
	-Wl,-soname,camera.gbrunch.so -o "$W/obj/camera.gbrunch.so"
O=$W/out
mkdir -p "$O/bin" "$O/vendor" "$O/lib64/libcamera/ipa" "$O/lib64/share/libcamera/ipa/softisp" "$O/lib64/etc/libcamera"
cp "$W/obj/gbcam-probe" "$O/bin/"
cp "$W/obj/camera.gbrunch.so" "$O/vendor/"
cp "$S/libcamera.so" "$S/libcamera-base.so" "$S/libcamera-hal.so" "$O/lib64/"
cp "$N/sysroot/usr/lib/x86_64-linux-android/libc++_shared.so" "$O/lib64/"
cp "$S/libcamera/ipa/ipa_softisp.so" "$O/lib64/libcamera/ipa/"
cp "$S/share/libcamera/ipa/softisp/uncalibrated.yaml" "$HERE/src/hi556.yaml" "$O/lib64/share/libcamera/ipa/softisp/"
cp "$HERE/src/camera_hal.yaml" "$O/lib64/etc/libcamera/"
find "$O" -type f \( -name '*.so' -o -path '*/bin/*' \) -exec "$N/bin/llvm-strip" --strip-unneeded {} +
(cd "$O" && find . -type f | sort | xargs sha256sum)
