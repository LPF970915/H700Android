#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix27
VERIFY_MOUNT=/mnt/rgsp-system-fix27-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX27_BACKUP

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
APEX_DIR=$SYSTEM_MOUNT/system/apex
test -d "$APEX_DIR/com.android.art.release"
test "$(strings "$APEX_DIR/com.android.art.release/apex_manifest.pb" | head -n 1)" = com.android.art
test ! -e "$APEX_DIR/com.android.art"
test ! -L "$APEX_DIR/com.android.art"
ln -s com.android.art.release "$APEX_DIR/com.android.art"
test "$(readlink "$APEX_DIR/com.android.art")" = com.android.art.release
printf 'system/apex/com.android.art -> com.android.art.release\n' > "$BACKUP_DIR/created-links"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test -L "$VERIFY_MOUNT/system/apex/com.android.art"
test "$(readlink "$VERIFY_MOUNT/system/apex/com.android.art")" = com.android.art.release
test -f "$VERIFY_MOUNT/system/apex/com.android.art/javalib/arm64/boot.art"
test -f "$VERIFY_MOUNT/system/apex/com.android.art/javalib/arm/boot.art"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix27
  echo PATCH_SEMANTICS='Expose the ART APEX under its manifest canonical name'
  cat "$BACKUP_DIR/created-links"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX27_SYSTEM_PREP.log
