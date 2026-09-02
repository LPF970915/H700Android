#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX16_LIBSELINUX_SHA=b80d7e10192a923126b5e9f82278b3a7603231722a1c546134fe6c13bbca7f61
FIX19_LIBSELINUX_SHA=bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix19
VERIFY_MOUNT=/mnt/rgsp-system-fix19-verify
PATCHED_LIB=/tmp/rgsp-android-libselinux-fix19.so
BACKUP_DIR=/mnt/sdcard/RGSP_FIX19_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$PATCHED_LIB" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
TARGET=$SYSTEM_MOUNT/system/lib64/libselinux.so
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX16_LIBSELINUX_SHA"
cp "$TARGET" "$BACKUP_DIR/libselinux.pre-fix19.so"
test "$(sha256sum "$BACKUP_DIR/libselinux.pre-fix19.so" | awk '{print $1}')" = "$FIX16_LIBSELINUX_SHA"
cp "$PATCHED_LIB" "$TARGET.fix19"
chmod --reference="$TARGET" "$TARGET.fix19"
chown --reference="$TARGET" "$TARGET.fix19"
mv "$TARGET.fix19" "$TARGET"
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-28
  echo FIX=fix19
  echo PREVIOUS_LIBSELINUX_SHA="$FIX16_LIBSELINUX_SHA"
  echo PATCHED_LIBSELINUX_SHA="$FIX19_LIBSELINUX_SHA"
  echo PATCH_SEMANTICS='SELinux-disabled status API compatibility for Binder managers'
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX19_SYSTEM_PREP.log
