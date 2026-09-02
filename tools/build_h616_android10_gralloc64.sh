#!/usr/bin/env bash
set -eo pipefail

SOURCE_ROOT=${H616_ANDROID_ROOT:-/home/lpf/H700Android/h616-android10-full}
PROJECT_ROOT=${H700_PROJECT_ROOT:-/mnt/d/Works/H700Android}
JOBS=${JOBS:-$(nproc)}
MODE=${1:-probe}
FORMAT_PATCH=$PROJECT_ROOT/tools/h616-gralloc-aarch64-format.patch
GRALLOC_SOURCE=hardware/aw/gpu/mali-bifrost/gralloc/src/mali_gralloc_bufferallocation.cpp

cd "$SOURCE_ROOT"

if grep -q 'sunxi format do not run here %lld' "$GRALLOC_SOURCE"; then
    patch -p1 < "$FORMAT_PATCH"
elif ! grep -q 'static_cast<unsigned long long>(bufDescriptor->hal_format)' "$GRALLOC_SOURCE"; then
    echo "unexpected H616 gralloc source; format patch cannot be verified" >&2
    exit 4
fi

# The Allwinner vendorsetup script expects Longan beside the Android tree. Its
# missing pack-tool path is irrelevant to a generic ARM64 module-only build.
set +e
source build/envsetup.sh >/tmp/h700-h616-envsetup.log 2>&1
ENVSETUP_RC=$?
set -e
if [[ $ENVSETUP_RC -ne 0 ]]; then
    cat /tmp/h700-h616-envsetup.log >&2
    exit "$ENVSETUP_RC"
fi

lunch aosp_arm64-userdebug >/tmp/h700-h616-lunch.log

TARGET_PRODUCT_VALUE=$(get_build_var TARGET_PRODUCT)
TARGET_ARCH_VALUE=$(get_build_var TARGET_ARCH)
TARGET_2ND_ARCH_VALUE=$(get_build_var TARGET_2ND_ARCH)
TARGET_BOARD_PLATFORM_VALUE=$(get_build_var TARGET_BOARD_PLATFORM)
PLATFORM_SDK_VERSION_VALUE=$(get_build_var PLATFORM_SDK_VERSION)
OUT_DIR_VALUE=$(get_build_var OUT_DIR)
MODULE_NAME=gralloc.cupid

printf 'source_root=%s\n' "$SOURCE_ROOT"
printf 'target_product=%s\n' "$TARGET_PRODUCT_VALUE"
printf 'target_arch=%s\n' "$TARGET_ARCH_VALUE"
printf 'target_2nd_arch=%s\n' "$TARGET_2ND_ARCH_VALUE"
printf 'target_board_platform=%s\n' "$TARGET_BOARD_PLATFORM_VALUE"
printf 'platform_sdk_version=%s\n' "$PLATFORM_SDK_VERSION_VALUE"
printf 'out_dir=%s\n' "$OUT_DIR_VALUE"
printf 'module_name=%s\n' "$MODULE_NAME"

if [[ "$MODE" == probe ]]; then
    exit 0
fi
if [[ "$MODE" != build ]]; then
    echo "usage: $0 [probe|build]" >&2
    exit 2
fi

TARGET_BOARD_PLATFORM=cupid \
TARGET_GPU_TYPE=mali-g31 \
mmm -j"$JOBS" hardware/aw/gpu/mali-bifrost/gralloc:"$MODULE_NAME"

OUTPUT=$(find "$OUT_DIR_VALUE" -type f -path '*/vendor/lib64/hw/gralloc.cupid.so' -print | head -n 1)
if [[ -z "$OUTPUT" ]]; then
    echo "64-bit gralloc output not found" >&2
    exit 3
fi

DESTINATION="$PROJECT_ROOT/out/fix51-h616/gralloc.cupid.so"
mkdir -p "$(dirname "$DESTINATION")"
cp -f "$OUTPUT" "$DESTINATION"

file "$OUTPUT"
sha256sum "$OUTPUT" "$DESTINATION"
readelf -d "$OUTPUT" | grep -E 'NEEDED|SONAME'
printf 'copied_to=%s\n' "$DESTINATION"
