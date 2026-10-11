#!/system/bin/sh
# VM-only diagnostic script; not a host command or a desktop-success test.
# Needs a locally installed init service and appropriate SELinux file/domain
# labels. Keep SELinux enforcing; audit denials before adding scoped rules.
sleep 80
echo GBRUNCH_NATIVE_STACK_CAPTURE
id
ls -l /dev/sw_sync /dev/dma_heap/*
for name in surfaceflinger android.hardware.composer.hwc3-service.drm bootanimation; do
    pid=$(pidof "$name")
    echo GBRUNCH_NATIVE_PROCESS "$name" "$pid"
    if [ -n "$pid" ]; then
        timeout 15 debuggerd -b "$pid"
        for task in /proc/$pid/task/*; do
            echo GBRUNCH_TASK "$task"
            cat "$task/comm" "$task/wchan" "$task/stack"
        done
    fi
done
echo GBRUNCH_NATIVE_STACK_END
