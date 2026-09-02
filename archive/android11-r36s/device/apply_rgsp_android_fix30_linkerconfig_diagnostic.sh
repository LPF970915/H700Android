#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
PRE_FIX30_INIT_RC_SHA=7a6f97b346a58f8f54fcb2cd0316cc36af3f91f1fa9e1c6258009353fb6573f1
WRAPPER_SHA=7c34a92720c1e6fbc80ad5bde91155bc27efd95d936ff99eafc9f029c61bdd6a
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix30
VERIFY_MOUNT=/mnt/rgsp-system-fix30-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX30_BACKUP
WRAPPER_SOURCE=/tmp/rgsp-linkerconfig-wrapper.fix30

test "$WRAPPER_SHA" != REPLACE_WRAPPER_SHA
test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$WRAPPER_SOURCE" | awk '{print $1}')" = "$WRAPPER_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
ART_LINK=$SYSTEM_MOUNT/system/apex/com.android.art
WRAPPER=$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-wrapper
test "$(sha256sum "$INIT_RC" | awk '{print $1}')" = "$PRE_FIX30_INIT_RC_SHA"
test -L "$ART_LINK"
test "$(readlink "$ART_LINK")" = com.android.art.release
cp "$INIT_RC" "$BACKUP_DIR/init.rc.pre-fix30"
printf 'system/apex/com.android.art -> %s\n' "$(readlink "$ART_LINK")" > "$BACKUP_DIR/removed-links"
rm "$ART_LINK"

cp "$WRAPPER_SOURCE" "$WRAPPER.fix30"
chown 0:0 "$WRAPPER.fix30"
chmod 0755 "$WRAPPER.fix30"
mv "$WRAPPER.fix30" "$WRAPPER"

sed 's#^    exec -- /system/bin/linkerconfig --target /linkerconfig/bootstrap$#    exec -- /system/bin/rgsp-linkerconfig-wrapper#' "$INIT_RC" > "$INIT_RC.fix30"
test "$(grep -Fxc '    exec -- /system/bin/rgsp-linkerconfig-wrapper' "$INIT_RC.fix30")" = 1
test "$(grep -Fxc '    exec -- /system/bin/linkerconfig --target /linkerconfig/bootstrap' "$INIT_RC.fix30")" = 0
chown --reference="$INIT_RC" "$INIT_RC.fix30"
chmod --reference="$INIT_RC" "$INIT_RC.fix30"
mv "$INIT_RC.fix30" "$INIT_RC"

sync
PATCHED_INIT_RC_SHA=$(sha256sum "$INIT_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test ! -e "$VERIFY_MOUNT/system/apex/com.android.art"
test ! -L "$VERIFY_MOUNT/system/apex/com.android.art"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-wrapper" | awk '{print $1}')" = "$WRAPPER_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$PATCHED_INIT_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix30
  echo PATCH_SEMANTICS='Remove duplicate ART APEX symlink and capture linkerconfig stderr'
  echo PRE_INIT_RC_SHA="$PRE_FIX30_INIT_RC_SHA"
  echo POST_INIT_RC_SHA="$PATCHED_INIT_RC_SHA"
  echo WRAPPER_SHA="$WRAPPER_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX30_SYSTEM_PREP.log
