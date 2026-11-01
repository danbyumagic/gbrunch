// SPDX-License-Identifier: Apache-2.0
/*
 * camera.gbrunch.so: the only GBRUNCH camera file in GBVENDOR (/vendor/lib64/hw).
 *
 * hw_get_module("camera") loads /vendor/lib64/hw/camera.<ro.hardware.camera>.so and reads its
 * HAL_MODULE_INFO_SYM. This module loads the real libcamera HAL from /vendor/lib64/libcamera, the
 * directory GBRUNCH bind-mounts from /oem/camera/lib64, and exposes a copy of its module struct. The
 * HAL itself can then be updated with GBRUNCH alone. The function pointers in the copy point into the
 * real HAL, which stays loaded for the life of the process.
 */
#include <dlfcn.h>
#include <string.h>

#include <android/log.h>
#include <hardware/camera_common.h>

#define REAL_HAL "/vendor/lib64/libcamera/libcamera-hal.so"

__attribute__((visibility("default"))) camera_module_t HAL_MODULE_INFO_SYM;

__attribute__((constructor)) static void gbrunch_camera_load(void)
{
	void *real = dlopen(REAL_HAL, RTLD_NOW | RTLD_LOCAL);
	const camera_module_t *hmi;

	if (!real) {
		__android_log_print(ANDROID_LOG_ERROR, "gbrunch-camera", "dlopen %s: %s", REAL_HAL, dlerror());
		return;
	}
	hmi = dlsym(real, HAL_MODULE_INFO_SYM_AS_STR);
	if (!hmi) {
		__android_log_print(ANDROID_LOG_ERROR, "gbrunch-camera", "no %s in %s", HAL_MODULE_INFO_SYM_AS_STR, REAL_HAL);
		return;
	}
	memcpy(&HAL_MODULE_INFO_SYM, hmi, sizeof(HAL_MODULE_INFO_SYM));
	__android_log_print(ANDROID_LOG_INFO, "gbrunch-camera", "loaded %s (%s)", REAL_HAL,
			    HAL_MODULE_INFO_SYM.common.name);
}
