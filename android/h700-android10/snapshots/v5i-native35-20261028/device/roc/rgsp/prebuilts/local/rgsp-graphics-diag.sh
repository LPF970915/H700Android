#!/system/bin/sh
export PATH=/system/bin:/system/xbin:/vendor/bin
DIR=/rgsp-persist/fix63
mkdir -p "$DIR"
exec >"$DIR/diagnostics.log" 2>&1
for delay in 30 60 90 120 300; do
    sleep "$delay"
    read uptime ignored < /proc/uptime
    stamp=${uptime%%.*}
    echo "=== uptime=$uptime ==="
    getprop sys.boot_completed
    getprop init.svc.bootanim
    ls -lZ /dev/mali0 /dev/ion /dev/disp /dev/graphics/fb0
    ps -A -o PID,NAME
    timeout 10 dumpsys SurfaceFlinger >"$DIR/surfaceflinger-$stamp.txt" 2>&1
    timeout 10 dumpsys window >"$DIR/window-$stamp.txt" 2>&1
    timeout 10 screencap -p "$DIR/screen-$stamp.png"
    echo "screencap_rc=$?"
    cat /sys/class/disp/disp/attr/sys
    sync
done
