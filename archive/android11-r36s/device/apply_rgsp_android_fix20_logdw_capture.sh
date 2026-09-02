#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX19_LIBSELINUX_SHA=bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984
ORIGINAL_LOGD_RC_SHA=ff0c7f55bbc6fec6cc8da29257c23cb2a4ba65b53cd6203628b2242d1fabdfd7
FIX20_LOGD_RC_SHA=2ea41acef64581cc67634afddd844c712e9745d8e664b258ce15d249cf66275d
FIX20_CAPTURE_SHA=6a31e4b79f1303261608eed23bb2258e6446dca4ab85fbf00c14416acc35472c

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix20
VERIFY_MOUNT=/mnt/rgsp-system-fix20-verify
CAPTURE_SOURCE=/tmp/rgsp-logdw-capture
RC_SOURCE=/tmp/logd.rc.fix20
BACKUP_DIR=/mnt/sdcard/RGSP_FIX20_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$CAPTURE_SOURCE" | awk '{print $1}')" = "$FIX20_CAPTURE_SHA"
test "$(sha256sum "$RC_SOURCE" | awk '{print $1}')" = "$FIX20_LOGD_RC_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
TARGET_RC=$SYSTEM_MOUNT/system/etc/init/logd.rc
TARGET_CAPTURE=$SYSTEM_MOUNT/system/bin/rgsp-logdw-capture
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
test "$(sha256sum "$TARGET_RC" | awk '{print $1}')" = "$ORIGINAL_LOGD_RC_SHA"
test ! -e "$TARGET_CAPTURE"
cp "$TARGET_RC" "$BACKUP_DIR/logd.rc.pre-fix20"
test "$(sha256sum "$BACKUP_DIR/logd.rc.pre-fix20" | awk '{print $1}')" = "$ORIGINAL_LOGD_RC_SHA"

cp "$CAPTURE_SOURCE" "$TARGET_CAPTURE.fix20"
chmod --reference="$SYSTEM_MOUNT/system/bin/logd" "$TARGET_CAPTURE.fix20"
chown --reference="$SYSTEM_MOUNT/system/bin/logd" "$TARGET_CAPTURE.fix20"
mv "$TARGET_CAPTURE.fix20" "$TARGET_CAPTURE"
test "$(sha256sum "$TARGET_CAPTURE" | awk '{print $1}')" = "$FIX20_CAPTURE_SHA"

cp "$RC_SOURCE" "$TARGET_RC.fix20"
chmod --reference="$TARGET_RC" "$TARGET_RC.fix20"
chown --reference="$TARGET_RC" "$TARGET_RC.fix20"
mv "$TARGET_RC.fix20" "$TARGET_RC"
test "$(sha256sum "$TARGET_RC" | awk '{print $1}')" = "$FIX20_LOGD_RC_SHA"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/logd.rc" | awk '{print $1}')" = "$FIX20_LOGD_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-logdw-capture" | awk '{print $1}')" = "$FIX20_CAPTURE_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-28
  echo FIX=fix20
  echo ORIGINAL_LOGD_RC_SHA="$ORIGINAL_LOGD_RC_SHA"
  echo PATCHED_LOGD_RC_SHA="$FIX20_LOGD_RC_SHA"
  echo LOGDW_CAPTURE_SHA="$FIX20_CAPTURE_SHA"
  echo SYSTEM_LIBSELINUX_SHA="$FIX19_LIBSELINUX_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX20_SYSTEM_PREP.log
