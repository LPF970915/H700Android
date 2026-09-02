#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
SF_DISABLED_SHA=656b9bf4c47f356a0be9ec0a7aa70ee4b16aa6887a86fc75a62852cc26bc57b3
BOOTANIM_DISABLED_SHA=d7854acbd566ba7985fefa5aa87602c42814ed5a7ea5904d2628ac4f9444f77f
ALLOC_RC_DISABLED_SHA=a139a3fd898f2c8404efbb51646814a2ec5cb848f8135bbc63d1b829c142037d
COMPOSER21_RC_DISABLED_SHA=2272ae38541f35caa05f7ca426f690e32b92c930622317e925e7796a29708bfa
COMPOSER22_RC_SHA=993bbbdf1efcefa1ef3c2853aa1e5a087eaa12f9c65027dfd0e6c00b9c8c2d74
COMPOSER22_BIN_SHA=151a9e533fee3c6301cd1bb794d35dad22e721764b3538cee22dda64be9cd22c
GRALLOC32_SHA=54e6515073238f18dcc8db832a73e8c43c36436710e76317a407eec6145ea8b2
GRALLOC64_SHA=3c040df46e4848b3a7ce74fbff585701e45f9349d87962d15fb0a189cd60f1b6
MALI32_SHA=05dc81f866b7ab947d20f283f25dcd96ca2f56ffd48e637b68778c1a994a6925
MALI64_SHA=03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix52
VERIFY_MOUNT=/mnt/rgsp-system-fix52-verify
DISABLED_INIT_DIR=system/rgsp-disabled-init/fix52
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX52_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

check_sha() {
  relative=$1
  expected=$2
  test "$(sha256sum "$SYSTEM_MOUNT/$relative" | awk '{print $1}')" = "$expected"
}

check_sha system/etc/init/surfaceflinger.rc.rk3326-disabled "$SF_DISABLED_SHA"
check_sha system/etc/init/bootanim.rc.rk3326-disabled "$BOOTANIM_DISABLED_SHA"
check_sha system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled "$ALLOC_RC_DISABLED_SHA"
check_sha system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled "$COMPOSER21_RC_DISABLED_SHA"
check_sha system/vendor/etc/init/android.hardware.graphics.composer@2.2-service.rc "$COMPOSER22_RC_SHA"
check_sha system/vendor/bin/hw/android.hardware.graphics.composer@2.2-service "$COMPOSER22_BIN_SHA"
check_sha system/vendor/lib/hw/gralloc.cupid.so "$GRALLOC32_SHA"
check_sha system/vendor/lib64/hw/gralloc.cupid.so "$GRALLOC64_SHA"
check_sha system/vendor/lib/egl/libGLES_mali.so "$MALI32_SHA"
check_sha system/vendor/lib64/egl/libGLES_mali.so "$MALI64_SHA"
test "$(grep -c '^ro.config.headless=' "$SYSTEM_MOUNT/system/build.prop")" = 0
test "$(grep -Fxc 'ro.hardware.gralloc=cupid' "$SYSTEM_MOUNT/system/vendor/build.prop")" = 1
test "$(grep -Fxc 'ro.hardware.hwcomposer=cupid' "$SYSTEM_MOUNT/system/vendor/build.prop")" = 1
test "$(grep -Fxc 'ro.hardware.egl=mali' "$SYSTEM_MOUNT/system/vendor/build.prop")" = 1

for relative in \
  system/etc/init/surfaceflinger.rc.rk3326-disabled \
  system/etc/init/bootanim.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled; do
  destination=$SYSTEM_MOUNT/$DISABLED_INIT_DIR/$relative
  mkdir -p "$(dirname "$destination")"
  mv "$SYSTEM_MOUNT/$relative" "$destination"
done

sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
for relative in \
  system/etc/init/surfaceflinger.rc.rk3326-disabled \
  system/etc/init/bootanim.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled; do
  test ! -e "$VERIFY_MOUNT/$relative"
  test -f "$VERIFY_MOUNT/$DISABLED_INIT_DIR/$relative"
done
test "$(sha256sum "$VERIFY_MOUNT/$DISABLED_INIT_DIR/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled" | awk '{print $1}')" = "$COMPOSER21_RC_DISABLED_SHA"
check_root=$VERIFY_MOUNT
test "$(sha256sum "$check_root/system/vendor/etc/init/android.hardware.graphics.composer@2.2-service.rc" | awk '{print $1}')" = "$COMPOSER22_RC_SHA"
test "$(sha256sum "$check_root/system/vendor/bin/hw/android.hardware.graphics.composer@2.2-service" | awk '{print $1}')" = "$COMPOSER22_BIN_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-09-02
  echo FIX=fix52
  echo BASELINE='H616 Android 10; H618 not used'
  echo CHANGE='moved legacy init rc files outside scanned init directories'
  echo COMPOSER22_RC_SHA="$COMPOSER22_RC_SHA"
  echo COMPOSER22_BIN_SHA="$COMPOSER22_BIN_SHA"
} | tee "$PREP_LOG"
