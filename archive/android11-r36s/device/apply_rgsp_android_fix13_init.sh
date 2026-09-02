#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
ORIGINAL_INIT_SHA=0d99036dd57083c19de4377c1590e9e7df033f8ced97b9659d7e483db96fc889
PATCHED_INIT_SHA=a5c26547268af6a0a6890fd305a8059fa222604e6e7b39ce9348e9ea97124289

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix13
PATCHED_INIT=/tmp/rgsp-android-init-fix13
BACKUP_DIR=/mnt/sdcard/RGSP_FIX13_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$PATCHED_INIT" | awk '{print $1}')" = "$PATCHED_INIT_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

TARGET=$SYSTEM_MOUNT/system/bin/init
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$ORIGINAL_INIT_SHA"
cp "$TARGET" "$BACKUP_DIR/init.pre-fix13"
cp "$PATCHED_INIT" "$TARGET.fix13"
chmod --reference="$TARGET" "$TARGET.fix13"
chown --reference="$TARGET" "$TARGET.fix13"
mv "$TARGET.fix13" "$TARGET"
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$PATCHED_INIT_SHA"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

{
  echo FIX=fix13
  echo ORIGINAL_INIT_SHA="$ORIGINAL_INIT_SHA"
  echo PATCHED_INIT_SHA="$PATCHED_INIT_SHA"
  echo PATCH_OFFSET=0xb27c8
  echo PATCH_SEMANTICS='SelinuxRestoreContext(): ret'
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX13_SYSTEM_PREP.log
