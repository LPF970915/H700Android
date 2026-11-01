#!/bin/bash
set -eo pipefail
root=$(realpath "${1:?Use tools/build_h700_low_pressure.ps1 -Execute}")
shift
test -f "$root/build/envsetup.sh"
test "$#" -gt 0
for target in "$@"; do
    case "$target" in systemimage|vendorimage|ramdisk|adbd|vold|services|Settings|SettingsIntelligence|SystemUI|MediaProvider|LatinIME|LeanbackIME|Calendar|DocumentsUI|RGSPLauncher|RGSPNavigation|H700Apps|H700Navigation|H700Input|H700KernelInput|H700Lid|H700Rotation|H700RotationFramework|H700ReleaseImage|H700ReleaseImageMT|H700Arm64Feasibility|H700Arm64Isolated|rgsp_vsync_probe|rgsp_egl_import_probe|hwcomposer.cupid|libsurfaceflinger|PermissionController) ;;
        H700DualAbiWindow|H700DualAbiBoot|H700DualAbiImage|H700DualAbiAudit|H700DualAbiBootEntry|H700DualAbiEntryImage|H700DualAbiHandoff|H700DualAbiHandoffImage|H700DualAbiTestNavigation|H700DualAbiTestImage|H700DualAbiTestAudit|H700DualAbiInteraction|H700DualAbiParity|H700DualAbiParityApps|H700DualAbiParityUi|H700DualAbiParityServices|H700DualAbiParityVold|H700DualAbiParityOverlay|H700DualAbiParityLinkage|H700DualAbiParityVoldAudit|H700DualAbiParitySettingsApi|H700DualAbiParityPayload|H700DualAbiParityStage|H700DualAbiParityFinal|H700DualAbiParitySeal|H700DualAbiParityImage) ;;
        H700DualAbiDefaultsStage|H700DualAbiDefaultsImage) ;;
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
if [ "$#" = 1 ] && [ "$1" = H700DualAbiDefaultsStage ]; then
    python3 "$(dirname "$(realpath "$0")")/interaction/seal_defaults.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiDefaultsImage ]; then
    python3 "$(dirname "$(realpath "$0")")/interaction/package_test2.py" --factory-defaults
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParitySeal ]; then
    python3 "$(dirname "$(realpath "$0")")/interaction/seal_stage.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityFinal ]; then
    python3 "$(dirname "$(realpath "$0")")/interaction/finalize_stage.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityImage ]; then
    python3 "$(dirname "$(realpath "$0")")/interaction/package_test2.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityStage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/prepare_stage.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityPayload ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/prepare_payload64.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParitySettingsApi ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/build_parity_settings_api.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityVoldAudit ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/audit_vold64.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityLinkage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/audit_parity_apis.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityOverlay ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/build_parity_overlay.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityServices ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/build_parity_services.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityUi ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/build_parity_systemui.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParityApps ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/build_parity_apps.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiParity ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/interaction/audit_parity.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiInteraction ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root" --prototype-interaction-only --interaction-label native-parity --interaction-version 12
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiTestAudit ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/audit_h700_dualabi_test1.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiTestNavigation ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/build_h700_apps.py" --source "$root" --prototype-navigation-only
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiTestImage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/package_h700_dualabi_test1.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiHandoffImage ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/package_h700_dualabi_entry_image.py" --handoff-p1b
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
if [ "$#" = 1 ] && [ "$1" = H700DualAbiHandoff ]; then
    echo "LOW_PRESSURE_START=$(date -Is)"
    python3 "$(dirname "$(realpath "$0")")/prepare_h700_dualabi_handoff.py"
    echo "LOW_PRESSURE_COMPLETE=$(date -Is)"
    exit 0
fi
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
if [ "$#" = 1 ] && { [ "$1" = H700DualAbiWindow ] || [ "$1" = H700DualAbiBoot ] || [ "$1" = H700DualAbiParityVold ]; }; then
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
    elif [ "$1" = H700DualAbiParityVold ]; then
        python3 "$(dirname "$(realpath "$0")")/interaction/check_vold_source.py"
        m -j1 vold
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
