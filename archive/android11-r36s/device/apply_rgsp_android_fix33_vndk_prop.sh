#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX30_CORE_INIT_RC_SHA=e87292a4d494d21eaa920f84ceea28094a94117301ee3f135b913ac919bc8a2e
FIX30_WRAPPER_SHA=7c34a92720c1e6fbc80ad5bde91155bc27efd95d936ff99eafc9f029c61bdd6a
FIX31_LATE_WRAPPER_SHA=7746d60acb368f076251d7bdfe76daf7ad085c715b1cc05819e8d7d16a3586ed

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix33
VERIFY_MOUNT=/mnt/rgsp-system-fix33-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX33_BACKUP
DEVICE_RC_REL=init.sun50iw9p1.rc
CORE_INIT_REL=system/etc/init/hw/init.rc

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

DEVICE_RC=$SYSTEM_MOUNT/$DEVICE_RC_REL
CORE_INIT_RC=$SYSTEM_MOUNT/$CORE_INIT_REL
test "$(sha256sum "$DEVICE_RC" | awk '{print $1}')" = "$FIX32_DEVICE_RC_SHA"
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX30_CORE_INIT_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-wrapper" | awk '{print $1}')" = "$FIX30_WRAPPER_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-late" | awk '{print $1}')" = "$FIX31_LATE_WRAPPER_SHA"
test "$(grep -Fxc '    exec -- /system/bin/rgsp-linkerconfig-wrapper' "$CORE_INIT_RC")" = 1
test "$(grep -Fxc '    setprop ro.vndk.version 30' "$CORE_INIT_RC")" = 0

cp "$CORE_INIT_RC" "$BACKUP_DIR/init.rc.pre-fix33"
awk '
  /    exec -- \/system\/bin\/rgsp-linkerconfig-wrapper/ && !inserted {
    print "    setprop ro.vndk.version 30"
    inserted=1
  }
  { print }
' "$CORE_INIT_RC" > "$CORE_INIT_RC.fix33"
test "$(grep -Fxc '    setprop ro.vndk.version 30' "$CORE_INIT_RC.fix33")" = 1
chown --reference="$CORE_INIT_RC" "$CORE_INIT_RC.fix33"
chmod --reference="$CORE_INIT_RC" "$CORE_INIT_RC.fix33"
mv "$CORE_INIT_RC.fix33" "$CORE_INIT_RC"

sync
PATCHED_CORE_INIT_SHA=$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(grep -Fxc '    setprop ro.vndk.version 30' "$VERIFY_MOUNT/$CORE_INIT_REL")" = 1
test "$(sha256sum "$VERIFY_MOUNT/$CORE_INIT_REL" | awk '{print $1}')" = "$PATCHED_CORE_INIT_SHA"
test "$(sha256sum "$VERIFY_MOUNT/$DEVICE_RC_REL" | awk '{print $1}')" = "$FIX32_DEVICE_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix33
  echo PATCH_SEMANTICS='Set ro.vndk.version before linkerconfig to satisfy VENDOR_VNDK_VERSION'
  echo PRE_CORE_INIT_SHA="$FIX30_CORE_INIT_RC_SHA"
  echo POST_CORE_INIT_SHA="$PATCHED_CORE_INIT_SHA"
  echo DEVICE_RC_SHA="$FIX32_DEVICE_RC_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX33_SYSTEM_PREP.log
