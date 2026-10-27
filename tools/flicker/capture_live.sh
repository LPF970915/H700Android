#!/system/bin/sh
# Safe flicker capture: samples backlight/PWM/display counters, logcat and raw input.
# Usage: sh capture_live.sh <dir> <seconds>
D=${1:-/data/local/tmp/flicker-live}
SECONDS=${2:-70}
rm -rf "$D"
mkdir -p "$D"
END=$(( $(date +%s) + SECONDS ))
(
  while [ "$(date +%s)" -lt "$END" ]; do
    T=$(date +%s.%N)
    B=$(cat /sys/class/backlight/*/brightness 2>/dev/null | head -1)
    S=$(cat /sys/class/disp/disp/attr/sys 2>/dev/null | tr '\n' ' ')
    echo "$T|$B|$S" >> "$D/samples.txt"
    sleep 0.1
  done
) &
( timeout "$SECONDS" logcat -b all -v time > "$D/logcat.txt" 2>&1 ) &
( timeout "$SECONDS" getevent -lt /dev/input/event0 /dev/input/event1 > "$D/input.txt" 2>&1 ) &
wait
echo DONE > "$D/done"
