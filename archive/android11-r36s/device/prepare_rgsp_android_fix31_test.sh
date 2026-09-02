#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX31_BOOT_SHA=e27240fed09f2438aad7afbc8728ac57a2b89d0ece9822d420c15f253301e335
FIX31_DEVICE_RC_SHA=790f76d2addf8e4088127a8c6095769ff7e43dfc4d0936adb1482ad9f438f895
FIX30_CORE_INIT_RC_SHA=e87292a4d494d21eaa920f84ceea28094a94117301ee3f135b913ac919bc8a2e
LATE_WRAPPER_SHA=7746d60acb368f076251d7bdfe76daf7ad085c715b1cc05819e8d7d16a3586ed

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix31.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix31-verify

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX31_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX31_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX30_CORE_INIT_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-late" | awk '{print $1}')" = "$LATE_WRAPPER_SHA"
test ! -e "$VERIFY_MOUNT/system/apex/com.android.art"
test ! -L "$VERIFY_MOUNT/system/apex/com.android.art"
test -d "$VERIFY_MOUNT/system/apex/com.android.art.release"
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log /mnt/sdcard/RGSP_ANDROID_LOGDW_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_POWERCTL_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_BOOTSTRAP_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_STDIO_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_LATE_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX31_BOOT_SHA"
printf 'fix31 one-shot 2026-08-29 device_rc=%s late_wrapper=%s boot=%s\n' \
  "$FIX31_DEVICE_RC_SHA" "$LATE_WRAPPER_SHA" "$FIX31_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-29
  echo FIX=fix31
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo SYSTEM_DEVICE_RC_SHA="$FIX31_DEVICE_RC_SHA"
  echo SYSTEM_CORE_INIT_RC_SHA="$FIX30_CORE_INIT_RC_SHA"
  echo SYSTEM_LATE_WRAPPER_SHA="$LATE_WRAPPER_SHA"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX31_DEVICE_PREP.log
