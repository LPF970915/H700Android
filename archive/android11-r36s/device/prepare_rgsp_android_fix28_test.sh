#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX28_BOOT_SHA=e45d4e0df169759ede0e2be2e0fbfe3479cad3a25d4a704026e103796725d542
ADB32_SHA=f0fdb1007a2cfd65107730b2b851316f80353a3709adc038d2bbdbc737fe6d97
ADB64_SHA=598a81a982950c4ec9d3f2e5b289aaf8e80d2d483c308b8475a4bc574ebe4b34

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix28.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix28-verify

test "$FIX28_BOOT_SHA" != REPLACE_FIX28_BOOT_SHA
test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX28_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test -L "$VERIFY_MOUNT/system/apex/com.android.art"
test "$(readlink "$VERIFY_MOUNT/system/apex/com.android.art")" = com.android.art.release
test "$(sha256sum "$VERIFY_MOUNT/system/lib/libadbconnection_client.so" | awk '{print $1}')" = "$ADB32_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libadbconnection_client.so" | awk '{print $1}')" = "$ADB64_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log /mnt/sdcard/RGSP_ANDROID_LOGDW_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_POWERCTL_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX28_BOOT_SHA"
printf 'fix28 one-shot 2026-08-29 adb32=%s adb64=%s boot=%s\n' \
  "$ADB32_SHA" "$ADB64_SHA" "$FIX28_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-29
  echo FIX=fix28
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo SYSTEM_ADB32_SHA="$ADB32_SHA"
  echo SYSTEM_ADB64_SHA="$ADB64_SHA"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX28_DEVICE_PREP.log
