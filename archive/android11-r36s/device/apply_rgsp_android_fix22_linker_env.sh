#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX19_LIBSELINUX_SHA=bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984
FIX20_LOGD_RC_SHA=2ea41acef64581cc67634afddd844c712e9745d8e664b258ce15d249cf66275d
FIX20_CAPTURE_SHA=6a31e4b79f1303261608eed23bb2258e6446dca4ab85fbf00c14416acc35472c
FIX21_INIT_RC_SHA=a26a584812227c1978b0c4caa8c20973bdd1d40dc5709c059a2864aef9d80577
ORIGINAL_LMKD_RC_SHA=2f8d28e5ba7deafaeeec0a46bc86390b0da965508a82593756f7d56743d8c5e4
ORIGINAL_NETD_RC_SHA=c558bb07806b29035f4d1093422c0e2afc574d3d15aa27654c3525cf8f2ac4cc
FIX22_LMKD_RC_SHA=12ee33255d895c8706d24eb3eaaec520a27b1fce4969012373047da1c79353c2
FIX22_NETD_RC_SHA=ef0bd6803b6f4215041b2ec3ad1ffa54311d7d494e3e7afe896f22c2adef0bd5

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix22
VERIFY_MOUNT=/mnt/rgsp-system-fix22-verify
LMKD_SOURCE=/tmp/lmkd.rc.fix22
NETD_SOURCE=/tmp/netd.rc.fix22
BACKUP_DIR=/mnt/sdcard/RGSP_FIX22_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$LMKD_SOURCE" | awk '{print $1}')" = "$FIX22_LMKD_RC_SHA"
test "$(sha256sum "$NETD_SOURCE" | awk '{print $1}')" = "$FIX22_NETD_RC_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

TARGET_LMKD=$SYSTEM_MOUNT/system/etc/init/lmkd.rc
TARGET_NETD=$SYSTEM_MOUNT/system/etc/init/netd.rc
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/etc/init/logd.rc" | awk '{print $1}')" = "$FIX20_LOGD_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/bin/rgsp-logdw-capture" | awk '{print $1}')" = "$FIX20_CAPTURE_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX21_INIT_RC_SHA"
test "$(sha256sum "$TARGET_LMKD" | awk '{print $1}')" = "$ORIGINAL_LMKD_RC_SHA"
test "$(sha256sum "$TARGET_NETD" | awk '{print $1}')" = "$ORIGINAL_NETD_RC_SHA"

cp "$TARGET_LMKD" "$BACKUP_DIR/lmkd.rc.pre-fix22"
cp "$TARGET_NETD" "$BACKUP_DIR/netd.rc.pre-fix22"
cp "$LMKD_SOURCE" "$TARGET_LMKD.fix22"
chmod --reference="$TARGET_LMKD" "$TARGET_LMKD.fix22"
chown --reference="$TARGET_LMKD" "$TARGET_LMKD.fix22"
mv "$TARGET_LMKD.fix22" "$TARGET_LMKD"
cp "$NETD_SOURCE" "$TARGET_NETD.fix22"
chmod --reference="$TARGET_NETD" "$TARGET_NETD.fix22"
chown --reference="$TARGET_NETD" "$TARGET_NETD.fix22"
mv "$TARGET_NETD.fix22" "$TARGET_NETD"
test "$(sha256sum "$TARGET_LMKD" | awk '{print $1}')" = "$FIX22_LMKD_RC_SHA"
test "$(sha256sum "$TARGET_NETD" | awk '{print $1}')" = "$FIX22_NETD_RC_SHA"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/lmkd.rc" | awk '{print $1}')" = "$FIX22_LMKD_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/netd.rc" | awk '{print $1}')" = "$FIX22_NETD_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix22
  echo PATCH_SEMANTICS='Expose statsd and resolver APEX libraries through service LD_LIBRARY_PATH'
  echo ORIGINAL_LMKD_RC_SHA="$ORIGINAL_LMKD_RC_SHA"
  echo PATCHED_LMKD_RC_SHA="$FIX22_LMKD_RC_SHA"
  echo ORIGINAL_NETD_RC_SHA="$ORIGINAL_NETD_RC_SHA"
  echo PATCHED_NETD_RC_SHA="$FIX22_NETD_RC_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX22_SYSTEM_PREP.log
