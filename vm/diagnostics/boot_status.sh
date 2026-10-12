#!/system/bin/sh
sleep 35
while true; do
 echo GBRUNCH_BOOT_STATUS_BEGIN
 for key in sys.boot_completed sys.cppreopt init.svc.cppreopts service.sf.prime_shader_cache; do
  echo "$key=$(getprop "$key")"
 done
 echo GBRUNCH_DATA_USAGE
 timeout 5 df -h /data
 echo GBRUNCH_PROCESS_LIST
 timeout 8 ps -A
 echo GBRUNCH_CRASH_LOG
 timeout 8 logcat -b crash -d -t 100
 echo GBRUNCH_PACKAGE_LOG
 timeout 8 logcat -b all -d -t 150 -s SystemServer:I PackageManager:I PackageManagerService:I ActivityManager:I ActivityTaskManager:I Watchdog:I cppreopts:I AndroidRuntime:E SurfaceFlinger:I
 echo GBRUNCH_DISPLAY_STATE
 timeout 10 dumpsys -t 5 SurfaceFlinger
 echo GBRUNCH_BOOT_STATUS_END
 sleep 60
done
