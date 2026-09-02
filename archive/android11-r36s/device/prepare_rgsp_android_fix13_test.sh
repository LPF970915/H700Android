#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX13_BOOT_SHA=e07522bfddc277b030c840aa5c4ded86da997778a94739b84a7f72f2f86301cd
FIX13_INIT_SHA=a5c26547268af6a0a6890fd305a8059fa222604e6e7b39ce9348e9ea97124289
FIX13_LIBSELINUX_SHA=fac1800b68852e92c90e05a03ae27987c6d926ed3b1f1a96d4497d81e76f3e46
FIX13_CORE_INIT_SHA=e75e168a438eb86a0086969e8ba901d6739bd786c7a54756d9268c021d17f697

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix13.img
BOOT_DEV=/dev/mmcblk0p4
ENV_DEV=/dev/mmcblk0p3
RECOVERY_IMAGE=/mnt/sdcard/rgsp-linux-boot-original.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
LOG=/mnt/sdcard/RGSP_ANDROID_FIX13_DEVICE_PREP.log
VERIFY_MOUNT=/mnt/rgsp-fix13-verify

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX13_BOOT_SHA"
test "$(sha256sum "$BOOT_DEV" | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if="$ENV_DEV" bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$RECOVERY_IMAGE" | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test -d "$VERIFY_MOUNT/rgsp-persist"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/init" | awk '{print $1}')" = "$FIX13_INIT_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX13_LIBSELINUX_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX13_CORE_INIT_SHA"
grep -Fqx 'import /init.sun50iw9p1.rc' "$VERIFY_MOUNT/system/etc/init/hw/init.rc"
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_POWERCTL_LAST.log
dd if="$BOOT_IMAGE" of="$BOOT_DEV" bs=1M conv=fsync
test "$(sha256sum "$BOOT_DEV" | awk '{print $1}')" = "$FIX13_BOOT_SHA"
printf 'fix13 one-shot 2026-08-28 init=%s boot=%s\n' \
  "$FIX13_INIT_SHA" "$FIX13_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-28
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum "$BOOT_DEV" | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if="$ENV_DEV" bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo RECOVERY_BOOT_SHA="$(sha256sum "$RECOVERY_IMAGE" | awk '{print $1}')"
  echo SYSTEM_INIT_SHA="$FIX13_INIT_SHA"
  echo SYSTEM_LIBSELINUX_SHA="$FIX13_LIBSELINUX_SHA"
  echo CORE_INIT_SHA="$FIX13_CORE_INIT_SHA"
  echo MARKER_SHA="$(sha256sum "$MARKER" | awk '{print $1}')"
} | tee "$LOG"
