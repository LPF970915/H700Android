#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX31_DEVICE_RC_SHA=790f76d2addf8e4088127a8c6095769ff7e43dfc4d0936adb1482ad9f438f895
FIX30_CORE_INIT_RC_SHA=e87292a4d494d21eaa920f84ceea28094a94117301ee3f135b913ac919bc8a2e
FIX30_WRAPPER_SHA=7c34a92720c1e6fbc80ad5bde91155bc27efd95d936ff99eafc9f029c61bdd6a
FIX31_LATE_WRAPPER_SHA=7746d60acb368f076251d7bdfe76daf7ad085c715b1cc05819e8d7d16a3586ed

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix32
VERIFY_MOUNT=/mnt/rgsp-system-fix32-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX32_BACKUP

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

APEX_DIR=$SYSTEM_MOUNT/system/apex
ART_RELEASE=$APEX_DIR/com.android.art.release
ART_CANONICAL=$APEX_DIR/com.android.art
DEVICE_RC=$SYSTEM_MOUNT/init.sun50iw9p1.rc
CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
WRAPPER=$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-wrapper
LATE_WRAPPER=$SYSTEM_MOUNT/system/bin/rgsp-linkerconfig-late

test "$(sha256sum "$DEVICE_RC" | awk '{print $1}')" = "$FIX31_DEVICE_RC_SHA"
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX30_CORE_INIT_RC_SHA"
test "$(sha256sum "$WRAPPER" | awk '{print $1}')" = "$FIX30_WRAPPER_SHA"
test "$(sha256sum "$LATE_WRAPPER" | awk '{print $1}')" = "$FIX31_LATE_WRAPPER_SHA"
test -d "$ART_RELEASE"
test ! -e "$ART_CANONICAL"
test "$(strings "$ART_RELEASE/apex_manifest.pb" | head -n 1)" = com.android.art

cp "$DEVICE_RC" "$BACKUP_DIR/init.sun50iw9p1.rc.pre-fix32"
cp "$ART_RELEASE/apex_manifest.pb" "$BACKUP_DIR/apex_manifest.pb"
printf 'system/apex/com.android.art.release -> system/apex/com.android.art\n' > "$BACKUP_DIR/art-rename"

mv "$ART_RELEASE" "$ART_CANONICAL"
sed 's#/apex/com\.android\.art\.release#/apex/com.android.art#g' "$DEVICE_RC" > "$DEVICE_RC.fix32"
test "$(grep -Fxc '    setenv LD_LIBRARY_PATH /apex/com.android.adbd/lib64:/apex/com.android.art/lib64:/apex/com.android.os.statsd/lib64:/apex/com.android.resolv/lib64:/system/lib64:/apex/com.android.adbd/lib:/apex/com.android.art/lib:/apex/com.android.os.statsd/lib:/apex/com.android.resolv/lib:/system/lib' "$DEVICE_RC.fix32")" = 2
test "$(grep -Fxc 'com.android.art.release' "$DEVICE_RC.fix32")" = 0
chown --reference="$DEVICE_RC" "$DEVICE_RC.fix32"
chmod --reference="$DEVICE_RC" "$DEVICE_RC.fix32"
mv "$DEVICE_RC.fix32" "$DEVICE_RC"

sync
PATCHED_DEVICE_RC_SHA=$(sha256sum "$DEVICE_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test -d "$VERIFY_MOUNT/system/apex/com.android.art"
test ! -e "$VERIFY_MOUNT/system/apex/com.android.art.release"
test "$(strings "$VERIFY_MOUNT/system/apex/com.android.art/apex_manifest.pb" | head -n 1)" = com.android.art
test "$(grep -Fxc 'com.android.art.release' "$VERIFY_MOUNT/init.sun50iw9p1.rc")" = 0
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$PATCHED_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX30_CORE_INIT_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-wrapper" | awk '{print $1}')" = "$FIX30_WRAPPER_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-linkerconfig-late" | awk '{print $1}')" = "$FIX31_LATE_WRAPPER_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix32
  echo PATCH_SEMANTICS='Expose flattened ART APEX at canonical com.android.art path and align device LD_LIBRARY_PATH'
  echo PRE_DEVICE_RC_SHA="$FIX31_DEVICE_RC_SHA"
  echo POST_DEVICE_RC_SHA="$PATCHED_DEVICE_RC_SHA"
  echo CORE_INIT_RC_SHA="$FIX30_CORE_INIT_RC_SHA"
  echo WRAPPER_SHA="$FIX30_WRAPPER_SHA"
  echo LATE_WRAPPER_SHA="$FIX31_LATE_WRAPPER_SHA"
  echo ART_PATH=system/apex/com.android.art
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX32_SYSTEM_PREP.log
