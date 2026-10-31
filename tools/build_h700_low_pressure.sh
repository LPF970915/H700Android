#!/bin/bash
set -eo pipefail
root=$(realpath "${1:?Use tools/build_h700_low_pressure.ps1 -Execute}")
shift
test -f "$root/build/envsetup.sh"
test "$#" -gt 0
for target in "$@"; do
    case "$target" in systemimage|vendorimage|ramdisk|adbd|vold|services|Settings|SettingsIntelligence|SystemUI|MediaProvider|LatinIME|LeanbackIME|Calendar|DocumentsUI|RGSPLauncher|RGSPNavigation|H700Apps|H700Navigation|H700Input|H700KernelInput|H700Lid|H700Rotation|H700RotationFramework|H700ReleaseImage|H700ReleaseImageMT|H700Arm64Feasibility|H700Arm64Isolated|rgsp_vsync_probe|rgsp_egl_import_probe|hwcomposer.cupid|libsurfaceflinger|PermissionController) ;;
        H700DualAbiWindow|H700DualAbiBoot|H700DualAbiImage|H700DualAbiAudit|H700DualAbiBootEntry|H700DualAbiEntryImage) ;;
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
test "$(df -Pk /mnt/d | awk 'NR == 2 {print $4}')" -ge 41943040
test "$(awk '/MemAvailable/ {print $2}' /proc/meminfo)" -ge 6291456
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 GOMAXPROCS=1
# Keep old Soong's Go heap below MemoryHigh during graph regeneration.
# This changes collection frequency; CPU, RAM and swap limits remain unchanged.
export GOGC=50
export JAVA_TOOL_OPTIONS='-Xmx2048m'
export NINJA_ARGS='-j1'
export MAKEFLAGS='-j1'
if [ "$#" = 1 ] && [ "$1" = H700DualAbiEntryImage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/package_h700_dualabi_entry_image.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiBootEntry ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/prepare_h700_dualabi_boot_entry.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiAudit ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/audit_h700_dualabi_image.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiImage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/package_h700_dualabi_prototype.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && { [ "$1" = H700DualAbiWindow ] || [ "$1" = H700DualAbiBoot ]; }; then
    # The dual-arch graph has more live Go data. Collect sooner instead of
    # raising MemoryHigh/MemoryMax or allowing extra CPUs.
    export GOGC=10
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/prepare_h700_dualabi_product.py"
    export OUT_DIR=/home/lpf/h700-dualabi-prototype-20261030/out
    cd "$root"
    source build/envsetup.sh >/dev/null
    lunch h700_rgsp64proto-eng
    if [ "$1" = H700DualAbiWindow ]; then
        m -j1 h700_window_probe gralloc.h700proto android.hardware.graphics.mapper@2.0-impl-2.1 linker libc.bootstrap libdl.bootstrap libm.bootstrap libGLESv1_CM libz H700AbiProbe64
        python3 "$(dirname "$(realpath "$0")")/build_h700_dualabi_bundle.py"
    else
        m -j1 init_second_stage adbd H700AbiProbe64
    fi
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700Arm64Isolated ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/prepare_h700_arm64_runtime.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700Arm64Feasibility ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/build_h700_arm64_feasibility.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700ReleaseImageMT ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/package_h700_v6b.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700ReleaseImage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/package_h700_v6a.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700RotationFramework ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/build_h700_rotation_framework.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700KernelInput ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/build_h700_kernel_input.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && { [ "$1" = H700Apps ] || [ "$1" = H700Input ] || [ "$1" = H700Navigation ] || [ "$1" = H700Lid ] || [ "$1" = H700Rotation ]; }; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    if [ "$1" = H700Rotation ]; then
        python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root" --rotation-only
    elif [ "$1" = H700Lid ]; then
        python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root" --lid-only
    elif [ "$1" = H700Input ]; then
        python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root" --input-only
    elif [ "$1" = H700Navigation ]; then
        python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root" --navigation-only
    else
        python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root"
    fi
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
cd "$root"
source build/envsetup.sh >/dev/null
lunch h700_rgsp-eng
echo "LOW_PRESSURE_START=$(date -Is)"
taskset -pc $$
m -j1 "$@"
echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
