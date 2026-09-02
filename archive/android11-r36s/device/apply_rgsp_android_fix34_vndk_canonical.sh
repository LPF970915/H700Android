#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX33_CORE_INIT_SHA=d5d5f8fb369abddc4a6d89bb3b230b9f57c5162c4c06ca3a7a4627c13c900eaa

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix34
VERIFY_MOUNT=/mnt/rgsp-system-fix34-verify
BACKUP_DIR=/tmp/RGSP_FIX34_BACKUP
PREP_LOG=/tmp/RGSP_ANDROID_FIX34_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

ART_DIR=$SYSTEM_MOUNT/system/apex/com.android.art
VNDK_CURRENT=$SYSTEM_MOUNT/system/apex/com.android.vndk.current
VNDK_CANONICAL=$SYSTEM_MOUNT/system/apex/com.android.vndk.v30
CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
test -d "$ART_DIR"
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX33_CORE_INIT_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX32_DEVICE_RC_SHA"
test -d "$VNDK_CURRENT"
test ! -e "$VNDK_CANONICAL"
test "$(strings "$VNDK_CURRENT/apex_manifest.pb" | head -n 1)" = com.android.vndk.v30

cp -a "$VNDK_CURRENT" "$BACKUP_DIR/com.android.vndk.current"
printf 'system/apex/com.android.vndk.current -> system/apex/com.android.vndk.v30\n' > "$BACKUP_DIR/vndk-rename"
mv "$VNDK_CURRENT" "$VNDK_CANONICAL"

sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test -d "$VERIFY_MOUNT/system/apex/com.android.vndk.v30"
test ! -e "$VERIFY_MOUNT/system/apex/com.android.vndk.current"
test "$(strings "$VERIFY_MOUNT/system/apex/com.android.vndk.v30/apex_manifest.pb" | head -n 1)" = com.android.vndk.v30
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX33_CORE_INIT_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX32_DEVICE_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix34
  echo PATCH_SEMANTICS='Rename VNDK APEX directory to manifest canonical name com.android.vndk.v30'
  echo CORE_INIT_SHA="$FIX33_CORE_INIT_SHA"
  echo DEVICE_RC_SHA="$FIX32_DEVICE_RC_SHA"
  echo VNDK_PATH=system/apex/com.android.vndk.v30
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
