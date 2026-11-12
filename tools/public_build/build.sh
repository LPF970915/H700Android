#!/bin/bash
# Run this through run-limited.sh. No historical receipt or personal key is used.
set -eo pipefail
[[ $# == 2 ]] || { echo 'Usage: build.sh SOURCE_ROOT OUTPUT_ROOT' >&2; exit 2; }
source_root=$(realpath "$1")
output_root=$(realpath -m "$2")
script_root=$(dirname "$(realpath "$0")")
test -f "$source_root/.roc-public/prepare.json"
test -L "$source_root/device/roc/roc_os_release_candidate/.private-signing"
[[ "$output_root" != "$source_root" && "$output_root" != "$source_root/"* ]] || exit 2
cg=$(awk -F: '$1 == "0" {print $3}' /proc/self/cgroup)
read -r quota period < "/sys/fs/cgroup$cg/cpu.max"
test "$quota" != max && test "$quota" -le "$period"
test "$(cat "/sys/fs/cgroup$cg/memory.max")" -le 6442450944
test "$(cat "/sys/fs/cgroup$cg/memory.swap.max")" -le 536870912
test "$(awk '/Cpus_allowed_list/ {print $2}' /proc/self/status)" = 0-1
test "$(ps -o ni= -p $$ | tr -d ' ')" = 19
mkdir -p "$output_root/host-compat/lib"
for lib in libncurses.so.5 libtinfo.so.5; do
    cp -L "$source_root/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8/sysroot/usr/lib/$lib" "$output_root/host-compat/lib/$lib"
done
export LD_LIBRARY_PATH="$output_root/host-compat/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OUT_DIR="$output_root"
export ROC_RELEASE_KEYS_DIR
ROC_RELEASE_KEYS_DIR=$(realpath "$source_root/device/roc/roc_os_release_candidate/.private-signing")
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 GOMAXPROCS=1 GOGC=10
export JAVA_TOOL_OPTIONS=-Xmx2048m NINJA_ARGS=-j1 MAKEFLAGS=-j1
cd "$source_root"
source build/envsetup.sh
lunch roc_os_release_candidate-user
test "$(get_build_var BOARD_PLAT_PRIVATE_SEPOLICY_DIR)" = 'device/softwinner/common/sepolicy/private device/roc/roc_os_release_candidate/sepolicy/private'
test -z "$(get_build_var PRODUCT_PRIVATE_SEPOLICY_DIRS)$(get_build_var PRODUCT_PUBLIC_SEPOLICY_DIRS)"
m -j1 systemimage vendorimage ramdisk
product="$OUT_DIR/target/product/roc_os_source64"
sha256sum "$product/system.img" "$product/vendor.img" "$product/ramdisk.img"
python3 "$script_root/record_build.py" --source "$source_root" --product "$product"
echo "ANDROID_PARTITIONS_BUILT=$product"
