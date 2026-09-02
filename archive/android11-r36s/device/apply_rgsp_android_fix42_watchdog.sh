#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX41_PROP_SHA=618a7a6413212b6a6f0ec7074564c258f76d8507080b72129e09a7a4a081aa66
FIX41_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
SERVICES_ORIGINAL_SHA=6e8d4e2273ddfae02ece98dead581bcedfeec11fd631cecd447c55da0010e8bc
SERVICES_PATCH_SHA=8cefb654cc391a20e10c0afc97f1780a3e1e6ccbda0feba4906fd2f52030cb92

PATCH=/mnt/sdcard/rgsp-services-watchdog-bypass.jar
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix42
VERIFY_MOUNT=/mnt/rgsp-system-fix42-verify
BACKUP_DIR=/tmp/RGSP_FIX42_BACKUP
PREP_LOG=/tmp/RGSP_ANDROID_FIX42_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$PATCH" | awk '{print $1}')" = "$SERVICES_PATCH_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

PROP_FILE=$SYSTEM_MOUNT/system/build.prop
DEVICE_RC=$SYSTEM_MOUNT/init.sun50iw9p1.rc
SERVICES_JAR=$SYSTEM_MOUNT/system/framework/services.jar
test "$(sha256sum "$PROP_FILE" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$DEVICE_RC" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$SERVICES_ORIGINAL_SHA" || \
  test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$SERVICES_PATCH_SHA"

if test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$SERVICES_ORIGINAL_SHA"; then
  cp "$SERVICES_JAR" "$BACKUP_DIR/services.jar.pre-fix42"
  chmod --reference="$SERVICES_JAR" "$PATCH"
  chown --reference="$SERVICES_JAR" "$PATCH"
  cp "$PATCH" "$SERVICES_JAR"
fi
test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$SERVICES_PATCH_SHA"
sync

umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"
mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/build.prop" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$SERVICES_PATCH_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix42
  echo PATCH_SEMANTICS='Bypass missing HIDL ServiceManager enumeration in system_server Watchdog'
  echo SERVICES_JAR_SHA="$SERVICES_PATCH_SHA"
  echo SYSTEM_BUILD_PROP_SHA="$FIX41_PROP_SHA"
  echo DEVICE_RC_SHA="$FIX41_DEVICE_RC_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
