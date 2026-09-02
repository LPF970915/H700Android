#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
PRE_FIX31_DEVICE_RC_SHA=58e4fade9fe9ed02f2f5d253e1c5240ed8932f51cf43888f4d278b769fe49999
FIX30_CORE_INIT_RC_SHA=e87292a4d494d21eaa920f84ceea28094a94117301ee3f135b913ac919bc8a2e
LATE_WRAPPER_SHA=7746d60acb368f076251d7bdfe76daf7ad085c715b1cc05819e8d7d16a3586ed
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix31
VERIFY_MOUNT=/mnt/rgsp-system-fix31-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX31_BACKUP
WRAPPER_SOURCE=/tmp/rgsp-linkerconfig-late.fix31

test "$LATE_WRAPPER_SHA" != REPLACE_LATE_WRAPPER_SHA
test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum "$WRAPPER_SOURCE" | awk '{print $1}')" = "$LATE_WRAPPER_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
DEVICE_RC=$SYSTEM_MOUNT/init.sun50iw9p1.rc
CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
LATE_WRAPPER=$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-late
test "$(sha256sum "$DEVICE_RC" | awk '{print $1}')" = "$PRE_FIX31_DEVICE_RC_SHA"
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX30_CORE_INIT_RC_SHA"
cp "$DEVICE_RC" "$BACKUP_DIR/init.sun50iw9p1.rc.pre-fix31"

cp "$WRAPPER_SOURCE" "$LATE_WRAPPER.fix31"
chown 0:0 "$LATE_WRAPPER.fix31"
chmod 0755 "$LATE_WRAPPER.fix31"
mv "$LATE_WRAPPER.fix31" "$LATE_WRAPPER"

cp "$DEVICE_RC" "$DEVICE_RC.fix31"
cat >> "$DEVICE_RC.fix31" <<'EOF'

# Run linkerconfig again after tombstoned is available so an early abort gets a tombstone.
on boot
    start rgsp-linkerconfig-late

service rgsp-linkerconfig-late /system/bin/rgsp-linkerconfig-late
    class core
    user root
    group root
    disabled
    oneshot
    stdio_to_kmsg
EOF
chown --reference="$DEVICE_RC" "$DEVICE_RC.fix31"
chmod --reference="$DEVICE_RC" "$DEVICE_RC.fix31"
mv "$DEVICE_RC.fix31" "$DEVICE_RC"
test "$(grep -Fxc '    start rgsp-linkerconfig-late' "$DEVICE_RC")" = 1
test "$(grep -Fxc 'service rgsp-linkerconfig-late /system/bin/rgsp-linkerconfig-late' "$DEVICE_RC")" = 1

sync
PATCHED_DEVICE_RC_SHA=$(sha256sum "$DEVICE_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$PATCHED_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-late" | awk '{print $1}')" = "$LATE_WRAPPER_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX30_CORE_INIT_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix31
  echo PATCH_SEMANTICS='Run linkerconfig after tombstoned startup to capture the abort backtrace'
  echo PRE_DEVICE_RC_SHA="$PRE_FIX31_DEVICE_RC_SHA"
  echo POST_DEVICE_RC_SHA="$PATCHED_DEVICE_RC_SHA"
  echo CORE_INIT_RC_SHA="$FIX30_CORE_INIT_RC_SHA"
  echo LATE_WRAPPER_SHA="$LATE_WRAPPER_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX31_SYSTEM_PREP.log
