#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX32_BOOT_SHA=39ec10fc0a7d3eb2fb3117afca44cdffbcbd86bcc6ed3a5f7eaa3818fd4dad31
FIX36_CORE_INIT_SHA=c54728c08b220603790b8ebd2211114ab3ac343309ab6ba0f80d8d16bf4112e9
FIX39_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX37_LIB64_SHA=fdc88b6bd7102ebcef0e172539fa85752f49077aef75eda8124c76175e96577c
FIX37_LIB32_SHA=0b466848ce61cc683407b7020815cb601b9b2111e4ab65ea987121fb0584692f
FIX38_HWB64_SHA=f3ffe369816dcd6ebc3c664980628089142ff39aa1a365abf9be63190d263a10
FIX38_HWB32_SHA=c2e3931ef763b8be78343f7b4931b85cec87c785066e81fe58c3561b44e7a997
ALLOC64_SHA=73c2ffc257e1e39825769fa66d8b53ff087c2e4de9e83c4778b44b61a7cef160
ALLOC32_SHA=914845eefb1f333044912f2ca49dcd9d08015e17de098e22afbe165476097549

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix32.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix41-verify

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX32_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX36_CORE_INIT_SHA"
test "$(sha256sum "$VERIFY_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX39_DEVICE_RC_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB32_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libhidlbase.so" | awk '{print $1}')" = "$FIX38_HWB64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib/libhidlbase.so" | awk '{print $1}')" = "$FIX38_HWB32_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/lib64/android.hardware.graphics.allocator@2.0.so" | awk '{print $1}')" = "$ALLOC64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/lib/android.hardware.graphics.allocator@2.0.so" | awk '{print $1}')" = "$ALLOC32_SHA"
test "$(grep -Fxc 'ro.config.headless=1' "$VERIFY_MOUNT/system/build.prop")" = 1
SERVICE_LIST=/tmp/rgsp-fix41-verify-services
find "$VERIFY_MOUNT" -type f -name 'surfaceflinger.rc*' -print > "$SERVICE_LIST"
test -s "$SERVICE_LIST"
while IFS= read -r SERVICE_RC; do
  test "$(grep -Fxc '    disabled' "$SERVICE_RC")" = 1
  test "$(grep -Fxc '    onrestart restart zygote' "$SERVICE_RC")" = 0
done < "$SERVICE_LIST"
! find "$VERIFY_MOUNT" -type f -name '*.rc*' -exec grep -l -F '    start surfaceflinger' {} \; 2>/dev/null
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log /mnt/sdcard/RGSP_ANDROID_LOGDW_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_POWERCTL_LAST.log /mnt/sdcard/RGSP_ANDROID_FIX41_SYSTEM_PREP.log

dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX32_BOOT_SHA"
printf 'fix41 one-shot 2026-08-30 boot=%s ro.config.headless=1 surfaceflinger=disabled\n' "$FIX32_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-30
  echo FIX=fix41
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo RO_CONFIG_HEADLESS=1
  echo SURFACEFLINGER_MODE=disabled
  echo BOOT_IMAGE_REUSED=fix32
} | tee /mnt/sdcard/RGSP_ANDROID_FIX41_DEVICE_PREP.log
