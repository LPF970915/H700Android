#!/system/bin/sh
# Fresh owned diagnostic files only; no display/power/sysfs settings are written.
set -eu
D=$1
duration=$2
case "$D" in /data/local/tmp/rgsp-flicker-final-*) ;; *) exit 2;; esac
case "$duration" in ''|*[!0-9]*) exit 2;; esac
[ "$duration" -ge 30 ] && [ "$duration" -le 1800 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
mkdir "$D"
cat /proc/sys/kernel/random/boot_id > "$D/boot-id"
pidof surfaceflinger > "$D/sf-pid-before"
dumpsys SurfaceFlinger > "$D/sf-before.txt"
end=$(( $(cut -d . -f 1 /proc/uptime) + duration ))
(
  while [ "$(cut -d . -f 1 /proc/uptime)" -lt "$end" ]; do
    echo "TIME $(cat /proc/uptime)"
    for node in /sys/class/backlight/*/brightness /sys/class/backlight/*/actual_brightness; do
      [ ! -f "$node" ] || { printf '%s=' "$node"; cat "$node"; }
    done
    cat /sys/class/disp/disp/attr/sys 2>/dev/null || true
    sleep 0.5
  done
) > "$D/samples.txt" &
( timeout "$duration" logcat -b all -v time > "$D/logcat.txt" 2>&1 || true ) &
( timeout "$duration" getevent -lt /dev/input/event0 > "$D/input-power.txt" 2>&1 || true ) &
( timeout "$duration" getevent -lt /dev/input/event1 > "$D/input-controller.txt" 2>&1 || true ) &
wait
pidof surfaceflinger > "$D/sf-pid-after"
dumpsys SurfaceFlinger > "$D/sf-after.txt"
echo DONE > "$D/done"
