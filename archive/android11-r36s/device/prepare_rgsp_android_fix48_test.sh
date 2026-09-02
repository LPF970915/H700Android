#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_BOOT_SHA=39ec10fc0a7d3eb2fb3117afca44cdffbcbd86bcc6ed3a5f7eaa3818fd4dad31
FIX41_PROP_SHA=618a7a6413212b6a6f0ec7074564c258f76d8507080b72129e09a7a4a081aa66
FIX41_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX48_SERVICES_SHA=08fbb4a1584cd244fa1fd96e172d548036957bf77e77552b125e82c1af02210c
FIX46_WATCH_SHA=b7264e878a3a9ee2c0a2d69b8010387803b44c95366260d91971929dc3fdecf1

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix32.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix48-verify
PREP_LOG=/tmp/RGSP_ANDROID_FIX48_DEVICE_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX32_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(df -Pk /mnt/sdcard | awk 'NR==2 {print $4}')" -gt 65536
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/build.prop" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX48_SERVICES_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-boot-watch.sh" | awk '{print $1}')" = "$FIX46_WATCH_SHA"
test "$(grep -Fxc 'ro.config.headless=1' "$VERIFY_MOUNT/system/build.prop")" = 1
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_FIX48_DEVICE_PREP.log \
  /mnt/sdcard/RGSP_ANDROID_FIX46_LMKD_DIAG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGDW_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX32_BOOT_SHA"
: > "$MARKER"
sync

{
  echo DATE=2026-09-01
  echo FIX=fix48
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo SERVICES_JAR_SHA="$FIX48_SERVICES_SHA"
  echo WATCH_SHA="$FIX46_WATCH_SHA"
  echo BOOT_IMAGE_REUSED=fix32
} | tee "$PREP_LOG"
