#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_BOOT_SHA=39ec10fc0a7d3eb2fb3117afca44cdffbcbd86bcc6ed3a5f7eaa3818fd4dad31
FIX54_FRAMEWORK_SHA=a8076efd6d57c8b6a0c31d60ff6a518fa7b63aa4de9992bcca3b93af3e16a851
FIX49_SERVICES_SHA=5b4ded60538f0a0a4903b56933eaa9527b11585028d9d9fc1e483fe52f8d3ce1
MALI_KBASE_SHA=987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9

FIX54_MANIFEST=/tmp/rgsp-fix54-payload.sha256
BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix32.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
SYSTEM_DEV=/dev/mmcblk1p2
DATA_DEV=/dev/mmcblk1p4
VERIFY_MOUNT=/mnt/rgsp-fix54-test-verify
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX54_DEVICE_PREP.log
ION_RULE='/dev/ion                    0777    system      graphics'
MALI_RULE='/dev/mali0                  0666    system      graphics'

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX32_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test -f "$FIX54_MANIFEST"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
findmnt -rn -S "$DATA_DEV" >/dev/null 2>&1 && exit 21
e2fsck -fn "$SYSTEM_DEV"

set +e
e2fsck -p "$DATA_DEV"
DATA_FSCK_RC=$?
set -e
case "$DATA_FSCK_RC" in
  0|1) ;;
  *) exit "$DATA_FSCK_RC" ;;
esac
e2fsck -fn "$DATA_DEV"

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
(cd "$VERIFY_MOUNT" && sha256sum -c "$FIX54_MANIFEST")
test "$(sha256sum "$VERIFY_MOUNT/system/framework/framework.jar" | awk '{print $1}')" = "$FIX54_FRAMEWORK_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/modules/mali_kbase.ko" | awk '{print $1}')" = "$MALI_KBASE_SHA"
test "$(grep -Fxc "$ION_RULE" "$VERIFY_MOUNT/system/etc/ueventd.rc")" = 1
test "$(grep -Fxc "$MALI_RULE" "$VERIFY_MOUNT/system/etc/ueventd.rc")" = 1
test ! -e "$VERIFY_MOUNT/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled"
test -f "$VERIFY_MOUNT/system/rgsp-disabled-init/fix52/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled"
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" \
  /mnt/sdcard/RGSP_ANDROID_FIX46_LMKD_DIAG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGDW_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX32_BOOT_SHA"
: > "$MARKER"
sync

{
  echo BUILD_DATE=2026-09-01
  echo DEVICE_DATE="$(date -Iseconds)"
  echo FIX=fix54
  echo BASELINE='H616 Android 10; H618 not used'
  echo FRAMEWORK_JAR_SHA="$FIX54_FRAMEWORK_SHA"
  echo ION_RULE="$ION_RULE"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo DATA_FSCK_RC="$DATA_FSCK_RC"
  echo BOOT_IMAGE_REUSED=fix32
} | tee "$PREP_LOG"
