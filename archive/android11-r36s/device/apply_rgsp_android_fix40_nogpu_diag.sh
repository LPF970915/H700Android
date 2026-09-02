#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX36_CORE_INIT_SHA=c54728c08b220603790b8ebd2211114ab3ac343309ab6ba0f80d8d16bf4112e9
FIX39_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX37_LIB64_SHA=fdc88b6bd7102ebcef0e172539fa85752f49077aef75eda8124c76175e96577c
FIX37_LIB32_SHA=0b466848ce61cc683407b7020815cb601b9b2111e4ab65ea987121fb0584692f
FIX38_HWB64_SHA=f3ffe369816dcd6ebc3c664980628089142ff39aa1a365abf9be63190d263a10
FIX38_HWB32_SHA=c2e3931ef763b8be78343f7b4931b85cec87c785066e81fe58c3561b44e7a997
ALLOC64_SHA=73c2ffc257e1e39825769fa66d8b53ff087c2e4de9e83c4778b44b61a7cef160
ALLOC32_SHA=914845eefb1f333044912f2ca49dcd9d08015e17de098e22afbe165476097549

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix40
VERIFY_MOUNT=/mnt/rgsp-system-fix40-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX40_BACKUP
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX40_SYSTEM_PREP.log

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

CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
DEVICE_RC=$SYSTEM_MOUNT/init.sun50iw9p1.rc
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX36_CORE_INIT_SHA"
test "$(sha256sum "$DEVICE_RC" | awk '{print $1}')" = "$FIX39_DEVICE_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB32_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libhidlbase.so" | awk '{print $1}')" = "$FIX38_HWB64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib/libhidlbase.so" | awk '{print $1}')" = "$FIX38_HWB32_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/lib64/android.hardware.graphics.allocator@2.0.so" | awk '{print $1}')" = "$ALLOC64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/lib/android.hardware.graphics.allocator@2.0.so" | awk '{print $1}')" = "$ALLOC32_SHA"
SERVICE_LIST=/tmp/rgsp-fix40-surfaceflinger-services
START_LIST=/tmp/rgsp-fix40-surfaceflinger-starts
find "$SYSTEM_MOUNT" -type f -name 'surfaceflinger.rc*' -print > "$SERVICE_LIST"
test -s "$SERVICE_LIST"
find "$SYSTEM_MOUNT" -type f -name '*.rc*' -exec grep -l -F '    start surfaceflinger' {} \; > "$START_LIST" || true

service_index=0
while IFS= read -r SERVICE_RC; do
  test -n "$SERVICE_RC"
  test "$(grep -Fxc 'service surfaceflinger /system/bin/surfaceflinger' "$SERVICE_RC")" = 1
  test "$(grep -Fxc '    class core animation' "$SERVICE_RC")" = 1
  test "$(grep -Fxc '    onrestart restart zygote' "$SERVICE_RC")" = 1
  test "$(grep -Fxc '    disabled' "$SERVICE_RC")" = 0
  service_index=$((service_index + 1))
  cp "$SERVICE_RC" "$BACKUP_DIR/surfaceflinger.rc.pre-fix40.$service_index"
  awk '
    /^    class core animation$/ {
      print
      print "    disabled"
      next
    }
    /^    onrestart restart zygote$/ { next }
    { print }
  ' "$SERVICE_RC" > "$SERVICE_RC.fix40"
  test "$(grep -Fxc '    disabled' "$SERVICE_RC.fix40")" = 1
  test "$(grep -Fxc '    onrestart restart zygote' "$SERVICE_RC.fix40")" = 0
  chown --reference="$SERVICE_RC" "$SERVICE_RC.fix40"
  chmod --reference="$SERVICE_RC" "$SERVICE_RC.fix40"
  mv "$SERVICE_RC.fix40" "$SERVICE_RC"
done < "$SERVICE_LIST"
test "$service_index" -ge 1

start_index=0
while IFS= read -r START_RC; do
  test -n "$START_RC"
  start_index=$((start_index + 1))
  rel=${START_RC#"$SYSTEM_MOUNT/"}
  cp "$START_RC" "$BACKUP_DIR/$(echo "$rel" | tr '/' '_').pre-fix40"
  awk '
    /^    start surfaceflinger$/ {
      print "    # fix40: SurfaceFlinger disabled until an ARM64 software EGL/GLES implementation is available"
      next
    }
    { print }
  ' "$START_RC" > "$START_RC.fix40"
  chown --reference="$START_RC" "$START_RC.fix40"
  chmod --reference="$START_RC" "$START_RC.fix40"
  mv "$START_RC.fix40" "$START_RC"
done < "$START_LIST"

sync
POST_SERVICE_SHA=$(sha256sum "$SERVICE_RC" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
find "$VERIFY_MOUNT" -type f -name 'surfaceflinger.rc*' -exec grep -L -F '    onrestart restart zygote' {} \; | grep -q .
! find "$VERIFY_MOUNT" -type f -name '*.rc*' -exec grep -l -F '    start surfaceflinger' {} \; 2>/dev/null
VERIFY_SERVICE_RC=$(find "$VERIFY_MOUNT" -type f -name 'surfaceflinger.rc*' | head -n 1)
test "$(grep -Fxc '    disabled' "$VERIFY_SERVICE_RC")" = 1
POST_SERVICE_SHA=$(sha256sum "$VERIFY_SERVICE_RC" | awk '{print $1}')
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix40
  echo PATCH_SEMANTICS='Disable the GLES-only SurfaceFlinger service and remove its zygote-killing onrestart hook for system_server isolation'
  echo SERVICE_FILES="$service_index"
  echo START_FILES="$start_index"
  echo POST_SERVICE_SHA="$POST_SERVICE_SHA"
  echo SOFTWARE_EGL_PRESENT=0
  echo SWIFTShader_PRESENT=0
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
