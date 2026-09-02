#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX29_BOOT_SHA=a4b3ee96fc97153cbcea28e88ca294e30ffeb72429a053eb78680a7739f5105a
FIX29_INIT_RC_SHA=7a6f97b346a58f8f54fcb2cd0316cc36af3f91f1fa9e1c6258009353fb6573f1

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix29.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix29-verify

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX29_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
TARGET=$VERIFY_MOUNT/system/etc/init/hw/init.rc
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX29_INIT_RC_SHA"
test "$(grep -Fxc '    mount none /system/apex /apex bind rec' "$TARGET")" = 2
grep -Fqx '    copy /linkerconfig/bootstrap/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_BOOTSTRAP_LAST.log' "$TARGET"
grep -Fqx '    copy /linkerconfig/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_LAST.log' "$TARGET"
test -L "$VERIFY_MOUNT/system/apex/com.android.art"
test "$(readlink "$VERIFY_MOUNT/system/apex/com.android.art")" = com.android.art.release
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log /mnt/sdcard/RGSP_ANDROID_LOGDW_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_POWERCTL_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_BOOTSTRAP_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX29_BOOT_SHA"
printf 'fix29 one-shot 2026-08-29 init_rc=%s boot=%s\n' \
  "$FIX29_INIT_RC_SHA" "$FIX29_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-29
  echo FIX=fix29
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo SYSTEM_INIT_RC_SHA="$FIX29_INIT_RC_SHA"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX29_DEVICE_PREP.log
