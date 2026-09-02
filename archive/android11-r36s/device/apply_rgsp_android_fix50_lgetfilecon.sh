#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX41_PROP_SHA=618a7a6413212b6a6f0ec7074564c258f76d8507080b72129e09a7a4a081aa66
FIX41_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX49_SERVICES_SHA=5b4ded60538f0a0a4903b56933eaa9527b11585028d9d9fc1e483fe52f8d3ce1
FIX19_LIBSELINUX_SHA=bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984
FIX50_LIBSELINUX_SHA=699d914d8228dc370993f56cdea07d04b6bc20c35033c0b3be5672954a659ef4

PATCH=/tmp/rgsp-libselinux-fix50.so
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix50
VERIFY_MOUNT=/mnt/rgsp-system-fix50-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX50_BACKUP
PREP_LOG=/tmp/RGSP_ANDROID_FIX50_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$PATCH" | awk '{print $1}')" = "$FIX50_LIBSELINUX_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

TARGET=$SYSTEM_MOUNT/system/lib64/libselinux.so
test "$(sha256sum "$SYSTEM_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA" || \
  test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX50_LIBSELINUX_SHA"

if test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"; then
  cp "$TARGET" "$BACKUP_DIR/libselinux.so.pre-fix50"
  test "$(sha256sum "$BACKUP_DIR/libselinux.so.pre-fix50" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
  cp "$PATCH" "$TARGET"
  chmod 0644 "$TARGET"
fi
sync
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX50_LIBSELINUX_SHA"

umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"
mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/build.prop" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX50_LIBSELINUX_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-09-01
  echo FIX=fix50
  echo PATCH_SEMANTICS='Return a freecon-safe compatibility context from lgetfilecon when SELinux is disabled'
  echo LIBSELINUX_SHA="$FIX50_LIBSELINUX_SHA"
  echo PREVIOUS_LIBSELINUX_SHA="$FIX19_LIBSELINUX_SHA"
  echo SERVICES_JAR_SHA="$FIX49_SERVICES_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
