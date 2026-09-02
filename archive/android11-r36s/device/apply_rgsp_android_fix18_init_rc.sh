#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX17_INIT_RC_SHA=e75e168a438eb86a0086969e8ba901d6739bd786c7a54756d9268c021d17f697
FIX18_INIT_RC_SHA=f2038ef115b7d01e5bf5e2f9dc7a080eb6b4a272ded72e33847dc506d7defad9

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix18
PATCHED_RC=/tmp/rgsp-init-rc-fix18
BACKUP_DIR=/mnt/sdcard/RGSP_FIX18_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$PATCHED_RC" | awk '{print $1}')" = "$FIX18_INIT_RC_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
TARGET=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX17_INIT_RC_SHA"
cp "$TARGET" "$BACKUP_DIR/init.rc.pre-fix18"
cp "$PATCHED_RC" "$TARGET.fix18"
chmod --reference="$TARGET" "$TARGET.fix18"
chown --reference="$TARGET" "$TARGET.fix18"
mv "$TARGET.fix18" "$TARGET"
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$FIX18_INIT_RC_SHA"
grep -Fqx '    mount none /system/apex /apex bind rec' "$TARGET"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

{
  echo FIX=fix18
  echo PREVIOUS_INIT_RC_SHA="$FIX17_INIT_RC_SHA"
  echo PATCHED_INIT_RC_SHA="$FIX18_INIT_RC_SHA"
  echo PATCH_SEMANTICS='rebind flattened APEX after update_linker_config'
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX18_SYSTEM_PREP.log
