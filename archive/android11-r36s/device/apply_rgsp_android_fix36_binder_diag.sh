#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX35_CORE_INIT_SHA=485019fda405358bd32cbd4be813787f338652c9070dddfd8d76aea68cfc23dc
FIX35_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
DIAG_SOURCE=/tmp/rgsp-binder-diagnostic-fix36
DIAG_SHA=8f546ef5923faed14f9cd74a66e071a7404f1139ca175fcb62a7d77537258227

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix36
VERIFY_MOUNT=/mnt/rgsp-system-fix36-verify
BACKUP_DIR=/root/RGSP_FIX36_BACKUP
PREP_LOG=/root/RGSP_ANDROID_FIX36_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
test "$(sha256sum "$DIAG_SOURCE" | awk '{print $1}')" = "$DIAG_SHA"
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
DIAG_TARGET=$SYSTEM_MOUNT/system/bin/rgsp-binder-diagnostic-fix36
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX35_CORE_INIT_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX35_DEVICE_RC_SHA"
test ! -e "$DIAG_TARGET"
test "$(grep -Fxc '    exec_background -- /system/bin/rgsp-binder-diagnostic-fix36' "$CORE_INIT_RC")" = 0

cp "$CORE_INIT_RC" "$BACKUP_DIR/init.rc.pre-fix36"
cp "$DIAG_SOURCE" "$DIAG_TARGET"
chown 0:0 "$DIAG_TARGET"
chmod 0755 "$DIAG_TARGET"

awk '
  /^on boot$/ {
    print
    print "    exec_background -- /system/bin/rgsp-binder-diagnostic-fix36"
    next
  }
  { print }
' "$CORE_INIT_RC" > "$CORE_INIT_RC.fix36"
test "$(grep -Fxc '    exec_background -- /system/bin/rgsp-binder-diagnostic-fix36' "$CORE_INIT_RC.fix36")" = 1
chown --reference="$CORE_INIT_RC" "$CORE_INIT_RC.fix36"
chmod --reference="$CORE_INIT_RC" "$CORE_INIT_RC.fix36"
mv "$CORE_INIT_RC.fix36" "$CORE_INIT_RC"

sync
POST_CORE_INIT_SHA=$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-binder-diagnostic-fix36" | awk '{print $1}')" = "$DIAG_SHA"
test "$(grep -Fxc '    exec_background -- /system/bin/rgsp-binder-diagnostic-fix36' "$VERIFY_MOUNT/system/etc/init/hw/init.rc")" = 1
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX35_DEVICE_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix36
  echo PATCH_SEMANTICS='Capture Binder failed transaction log, manager fds, and device node state'
  echo PRE_CORE_INIT_SHA="$FIX35_CORE_INIT_SHA"
  echo POST_CORE_INIT_SHA="$POST_CORE_INIT_SHA"
  echo DIAG_SHA="$DIAG_SHA"
  echo DEVICE_RC_SHA="$FIX35_DEVICE_RC_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
