#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX30_BOOT_SHA=809a027a37c510db82083772ffbdfa3df745a6978c9608628836528d37d84338
FIX30_INIT_RC_SHA=e87292a4d494d21eaa920f84ceea28094a94117301ee3f135b913ac919bc8a2e
WRAPPER_SHA=7c34a92720c1e6fbc80ad5bde91155bc27efd95d936ff99eafc9f029c61bdd6a

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix30.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix30-verify

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX30_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX30_INIT_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-wrapper" | awk '{print $1}')" = "$WRAPPER_SHA"
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
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_STDIO_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX30_BOOT_SHA"
printf 'fix30 one-shot 2026-08-29 init_rc=%s wrapper=%s boot=%s\n' \
  "$FIX30_INIT_RC_SHA" "$WRAPPER_SHA" "$FIX30_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-29
  echo FIX=fix30
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo SYSTEM_INIT_RC_SHA="$FIX30_INIT_RC_SHA"
  echo SYSTEM_WRAPPER_SHA="$WRAPPER_SHA"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX30_DEVICE_PREP.log
