#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX33_CORE_INIT_SHA=d5d5f8fb369abddc4a6d89bb3b230b9f57c5162c4c06ca3a7a4627c13c900eaa
FIX30_WRAPPER_SHA=7c34a92720c1e6fbc80ad5bde91155bc27efd95d936ff99eafc9f029c61bdd6a
FIX31_LATE_WRAPPER_SHA=7746d60acb368f076251d7bdfe76daf7ad085c715b1cc05819e8d7d16a3586ed

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix35
VERIFY_MOUNT=/mnt/rgsp-system-fix35-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX35_BACKUP
PATCH_SOURCE=/tmp/rgsp-linkerconfig-default-fix35
PATCH_SHA=3e38946ac5befb7599a7f43889c1c4bbd47f6bf0a94575d5112b6925578bce1e
PREP_LOG=/tmp/RGSP_ANDROID_FIX35_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
test "$(sha256sum "$PATCH_SOURCE" | awk '{print $1}')" = "$PATCH_SHA"
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
PATCH_TARGET=$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-default-fix35
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX33_CORE_INIT_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX32_DEVICE_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-wrapper" | awk '{print $1}')" = "$FIX30_WRAPPER_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-late" | awk '{print $1}')" = "$FIX31_LATE_WRAPPER_SHA"
test "$(grep -Fxc '    exec -- /system/bin/rgsp-linkerconfig-wrapper' "$CORE_INIT_RC")" = 1
test "$(grep -Fxc '    setprop ro.vndk.version 30' "$CORE_INIT_RC")" = 1
test "$(grep -Fxc '    mount none /system/apex /apex bind rec' "$CORE_INIT_RC")" = 2
test ! -e "$PATCH_TARGET"

cp "$CORE_INIT_RC" "$BACKUP_DIR/init.rc.pre-fix35"
cp "$PATCH_SOURCE" "$PATCH_TARGET"
chown 0:0 "$PATCH_TARGET"
chmod 0755 "$PATCH_TARGET"

awk '
  /^    mount none \/system\/apex \/apex bind rec$/ {
    rebind++
    print
    if (rebind == 2) {
      print "    exec -- /system/bin/rgsp-linkerconfig-default-fix35"
      print "    mount none /linkerconfig/default /linkerconfig bind rec"
    }
    next
  }
  { print }
  END { if (rebind != 2) exit 42 }
' "$CORE_INIT_RC" > "$CORE_INIT_RC.fix35"
test "$(grep -Fxc '    exec -- /system/bin/rgsp-linkerconfig-default-fix35' "$CORE_INIT_RC.fix35")" = 1
test "$(grep -Fxc '    mount none /linkerconfig/default /linkerconfig bind rec' "$CORE_INIT_RC.fix35")" = 1
chown --reference="$CORE_INIT_RC" "$CORE_INIT_RC.fix35"
chmod --reference="$CORE_INIT_RC" "$CORE_INIT_RC.fix35"
mv "$CORE_INIT_RC.fix35" "$CORE_INIT_RC"

sync
PATCHED_CORE_INIT_SHA=$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-default-fix35" | awk '{print $1}')" = "$PATCH_SHA"
test "$(grep -Fxc '    exec -- /system/bin/rgsp-linkerconfig-default-fix35' "$VERIFY_MOUNT/system/etc/init/hw/init.rc")" = 1
test "$(grep -Fxc '    mount none /linkerconfig/default /linkerconfig bind rec' "$VERIFY_MOUNT/system/etc/init/hw/init.rc")" = 1
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$PATCHED_CORE_INIT_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX32_DEVICE_RC_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix35
  echo PATCH_SEMANTICS='Add ART javalib to default linker namespace after update_linker_config and activate default config'
  echo PRE_CORE_INIT_SHA="$FIX33_CORE_INIT_SHA"
  echo POST_CORE_INIT_SHA="$PATCHED_CORE_INIT_SHA"
  echo PATCH_SHA="$PATCH_SHA"
  echo DEVICE_RC_SHA="$FIX32_DEVICE_RC_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
