#!/system/bin/sh
sleep 35
while true; do
 echo GBRUNCH_BOOT_STATUS_BEGIN
 for key in sys.boot_completed sys.cppreopt init.svc.cppreopts service.sf.prime_shader_cache; do
  echo "$key=$(getprop "$key")"
 done
 df -h /data
 ps -A
 logcat -b crash -d -t 100
 logcat -b all -d -t 150 -s SystemServer:I PackageManager:I PackageManagerService:I ActivityManager:I ActivityTaskManager:I Watchdog:I cppreopts:I AndroidRuntime:E SurfaceFlinger:I
 timeout 10 dumpsys -t 5 SurfaceFlinger
 echo GBRUNCH_BOOT_STATUS_END
 sleep 60
done
