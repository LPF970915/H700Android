#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX11_LIBSELINUX_SHA=fac1800b68852e92c90e05a03ae27987c6d926ed3b1f1a96d4497d81e76f3e46
FIX16_LIBSELINUX_SHA=b80d7e10192a923126b5e9f82278b3a7603231722a1c546134fe6c13bbca7f61

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix16
PATCHED_LIB=/tmp/rgsp-android-libselinux-fix16.so
BACKUP_DIR=/mnt/sdcard/RGSP_FIX16_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$PATCHED_LIB" | awk '{print $1}')" = "$FIX16_LIBSELINUX_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
TARGET=$SYSTEM_MOUNT/system/lib64/libselinux.so
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX11_LIBSELINUX_SHA"
cp "$TARGET" "$BACKUP_DIR/libselinux.pre-fix16.so"
cp "$PATCHED_LIB" "$TARGET.fix16"
chmod --reference="$TARGET" "$TARGET.fix16"
chown --reference="$TARGET" "$TARGET.fix16"
mv "$TARGET.fix16" "$TARGET"
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX16_LIBSELINUX_SHA"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

{
  echo FIX=fix16
  echo PREVIOUS_LIBSELINUX_SHA="$FIX11_LIBSELINUX_SHA"
  echo PATCHED_LIBSELINUX_SHA="$FIX16_LIBSELINUX_SHA"
  echo PATCH_SEMANTICS='SELinux-disabled kernel compatibility for Android init contexts'
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX16_SYSTEM_PREP.log
