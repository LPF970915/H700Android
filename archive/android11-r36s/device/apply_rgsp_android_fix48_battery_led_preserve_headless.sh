#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_BOOT_SHA=39ec10fc0a7d3eb2fb3117afca44cdffbcbd86bcc6ed3a5f7eaa3818fd4dad31
FIX41_PROP_SHA=618a7a6413212b6a6f0ec7074564c258f76d8507080b72129e09a7a4a081aa66
FIX41_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX47_SERVICES_SHA=f1ba3b4f9bb275956a45fb610e59cb7d1603bb9aa2ebe5592a28e1002b32c5ec
FIX48_SERVICES_SHA=08fbb4a1584cd244fa1fd96e172d548036957bf77e77552b125e82c1af02210c

PATCH=/tmp/rgsp-services-fix48.jar
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix48
VERIFY_MOUNT=/mnt/rgsp-system-fix48-verify
BACKUP_DIR=/tmp/RGSP_FIX48_BACKUP
PREP_LOG=/tmp/RGSP_ANDROID_FIX48_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/roms/rgsp-android11-handoff-boot-fix32.img | awk '{print $1}')" = "$FIX32_BOOT_SHA"
test "$(sha256sum "$PATCH" | awk '{print $1}')" = "$FIX48_SERVICES_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

SERVICES_JAR=$SYSTEM_MOUNT/system/framework/services.jar
test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$FIX47_SERVICES_SHA" || \
  test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$FIX48_SERVICES_SHA"

if test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$FIX47_SERVICES_SHA"; then
  cp "$SERVICES_JAR" "$BACKUP_DIR/services.jar.pre-fix48"
  cp "$PATCH" "$SERVICES_JAR"
  chmod 0644 "$SERVICES_JAR"
fi
sync
test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$FIX48_SERVICES_SHA"

umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"
mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/build.prop" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX48_SERVICES_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-09-01
  echo FIX=fix48
  echo PATCH_SEMANTICS='Add headless BatteryService LED guard while preserving the fix45 classes.dex baseline'
  echo SERVICES_JAR_SHA="$FIX48_SERVICES_SHA"
  echo PREVIOUS_SERVICES_JAR_SHA="$FIX47_SERVICES_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
