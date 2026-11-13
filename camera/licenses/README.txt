Licenses of the camera stack built by camera/build.sh (installed to /oem/camera on GBRUNCH).

Component        Version (pinned in camera/build.sh)          License                         File
libcamera        df8e348d64b4932a0676256ed24f0da3ee9438bc      LGPL-2.1-or-later (library and   libcamera-LGPL-2.1-or-later.txt
                 https://gitlab.freedesktop.org/camera/libcamera  Android HAL); Apache-2.0 for     libcamera-Apache-2.0.txt
                                                                its Android headers
libyuv           500f45652c459cfccd20f83f297eb66cb7b015cb      BSD-3-Clause                    libyuv-LICENSE
                 (libcamera subprojects/libyuv.wrap)
libyaml          0.2.5 (libcamera subprojects/libyaml.wrap)    MIT                             libyaml-License
libjpeg-turbo    3.2.1                                         IJG, BSD-3-Clause, zlib         libjpeg-turbo-LICENSE.md,
                                                                                               libjpeg-turbo-README.ijg
libexif          0.6.26                                        LGPL-2.1-or-later               libexif-COPYING
libc++_shared.so Android NDK r30                               Apache-2.0 WITH LLVM-exception  libcxx-LICENSE.TXT
gbcam-probe      this repository (camera/src/gbcam_probe.cpp)   GPL-2.0-or-later                GPL-2.0.txt (release kit)
camera.gbrunch.so this repository (camera/src/camera_gbrunch_trampoline.c)  Apache-2.0           libcamera-Apache-2.0.txt
*.yaml           this repository (camera/src)                  CC0-1.0

libyuv, libyaml, libjpeg-turbo and libexif are linked statically into libcamera-hal.so / libcamera.so.
Corresponding source: camera/build.sh downloads every source above by URL and hash, applies
camera/patches, and rebuilds the same bytes (the output is reproducible; prepare_profile_assets.py
pins each file's sha256). libcxx-LICENSE.TXT is llvm-project libcxx/LICENSE.TXT; the other texts are
taken from the pinned revisions.
