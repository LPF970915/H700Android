#!/bin/bash
set -eo pipefail
root=$(realpath "${1:?Use tools/build_h700_low_pressure.ps1 -Execute}")
shift
test -f "$root/build/envsetup.sh"
test "$#" -gt 0
for target in "$@"; do
    case "$target" in systemimage|vendorimage|ramdisk|LeanbackIME|DocumentsUI) ;;
        *) echo "Unsupported target: $target" >&2; exit 2 ;;
    esac
done
# Refuse direct, unconstrained execution of this build entry point.
cg=$(awk -F: '$1 == "0" {print $3}' /proc/self/cgroup)
test -n "$cg"
test "$(cat "/sys/fs/cgroup$cg/memory.max")" -le 6442450944
read -r quota period < "/sys/fs/cgroup$cg/cpu.max"
test "$quota" != max
test "$quota" -le "$period"
test "$(awk '/Cpus_allowed_list/ {print $2}' /proc/self/status)" = 0-1
test "$(ps -o ni= -p $$ | tr -d ' ')" = 19
exec 9>/tmp/h700-android10-low-pressure.lock
flock -n 9 || { echo 'Another low-pressure build is running' >&2; exit 1; }
test "$(df -Pk /mnt/d | awk 'NR == 2 {print $4}')" -ge 125829120
test "$(awk '/MemAvailable/ {print $2}' /proc/meminfo)" -ge 6291456
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 GOMAXPROCS=1
export JAVA_TOOL_OPTIONS='-XX:ActiveProcessorCount=1 -Xmx2048m'
export NINJA_ARGS='-j1'
export MAKEFLAGS='-j1'
cd "$root"
source build/envsetup.sh >/dev/null
lunch h700_rgsp-eng
echo "LOW_PRESSURE_START=$(date -Is)"
taskset -pc $$
m -j1 "$@"
echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
