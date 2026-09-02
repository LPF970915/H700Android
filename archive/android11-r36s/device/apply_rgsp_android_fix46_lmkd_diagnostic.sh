#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_BOOT_SHA=39ec10fc0a7d3eb2fb3117afca44cdffbcbd86bcc6ed3a5f7eaa3818fd4dad31
FIX41_PROP_SHA=618a7a6413212b6a6f0ec7074564c258f76d8507080b72129e09a7a4a081aa66
FIX41_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX45_SERVICES_SHA=f599d998d66ef8d9dad1803fc2e553d4ff26538f20b62412a49e3ec76edd42b2
PREVIOUS_WATCH_SHA=cd581144800011630569e65b5001793060bb6f22e21048e192e85a6e156d0858
FIX46_WATCH_SHA=b7264e878a3a9ee2c0a2d69b8010387803b44c95366260d91971929dc3fdecf1

PATCH=/tmp/rgsp-boot-watch-fix46.sh
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix46
VERIFY_MOUNT=/mnt/rgsp-system-fix46-verify
BACKUP_DIR=/tmp/RGSP_FIX46_BACKUP
PREP_LOG=/tmp/RGSP_ANDROID_FIX46_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/roms/rgsp-android11-handoff-boot-fix32.img | awk '{print $1}')" = "$FIX32_BOOT_SHA"
test "$(sha256sum "$PATCH" | awk '{print $1}')" = "$FIX46_WATCH_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

WATCH=$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh
test "$(sha256sum "$SYSTEM_MOUNT/system/build.prop" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX45_SERVICES_SHA"
test "$(sha256sum "$WATCH" | awk '{print $1}')" = "$PREVIOUS_WATCH_SHA" || \
  test "$(sha256sum "$WATCH" | awk '{print $1}')" = "$FIX46_WATCH_SHA"

if test "$(sha256sum "$WATCH" | awk '{print $1}')" = "$PREVIOUS_WATCH_SHA"; then
  cp "$WATCH" "$BACKUP_DIR/rgsp-boot-watch.sh.pre-fix46"
  cp "$PATCH" "$WATCH"
  chmod 0755 "$WATCH"
fi
sync
test "$(sha256sum "$WATCH" | awk '{print $1}')" = "$FIX46_WATCH_SHA"

umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"
mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/build.prop" | awk '{print $1}')" = "$FIX41_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX41_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX45_SERVICES_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/bin/rgsp-boot-watch.sh" | awk '{print $1}')" = "$FIX46_WATCH_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-31
  echo FIX=fix46
  echo PATCH_SEMANTICS='Stop lmkd before zygote and capture system_server memory, PSI, oom score, dmesg, and text logcat'
  echo WATCH_SHA="$FIX46_WATCH_SHA"
  echo SERVICES_JAR_SHA="$FIX45_SERVICES_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
