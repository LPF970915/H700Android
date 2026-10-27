#!/system/bin/sh
# Bounded observation only. Records real input events; never injects any.
set -u
export PATH=/system/bin:/vendor/bin
tag=${1:?Unique evidence tag required}
case "$tag" in *[!A-Za-z0-9_-]*|'') exit 2 ;; esac
directory=/data/local/tmp/rgsp-display-$tag
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ] || exit 3
[ ! -e "$directory" ] || exit 4
mkdir "$directory" || exit 5
stamp=$(date '+%m-%d %H:%M:%S.000')
{
    echo "START=$stamp"
    getprop ro.build.fingerprint
    uname -a
    settings get system screen_brightness
    settings get system screen_brightness_mode
    getprop persist.vendor.hwc.software_vsync
    cat /sys/kernel/debug/clk/clk_summary
} > "$directory/metadata.txt"
timeout 60 logcat -b all -v monotonic -T "$stamp" 2>&1 |
    grep -iE 'hwc|vsync|blank|swap.display|hotplug|fence|DisplayPowerController|screen_toggled|PowerManagerService' > "$directory/display-logcat.txt" &
log_pid=$!
timeout 60 getevent -lt /dev/input/event0 > "$directory/power-events.txt" 2>&1 &
power_pid=$!
timeout 60 getevent -lt /dev/input/event1 > "$directory/controller-events.txt" 2>&1 &
keys_pid=$!
cleanup() { kill "$log_pid" "$power_pid" "$keys_pid" 2>/dev/null || true; }
trap cleanup EXIT HUP TERM
sample=0
while [ "$sample" -lt 250 ]; do
    {
        echo "SAMPLE=$sample"
        cat /proc/uptime
        head -n 7 /sys/class/disp/disp/attr/sys
        head -n 3 /sys/kernel/debug/pwm
        grep 'dispaly' /proc/interrupts
        if [ $((sample % 10)) -eq 0 ]; then
            cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
        fi
    } >> "$directory/samples.txt"
    sample=$((sample + 1))
    sleep .1
done
echo "DISPLAY_OBSERVATION_COMPLETE=$directory"
