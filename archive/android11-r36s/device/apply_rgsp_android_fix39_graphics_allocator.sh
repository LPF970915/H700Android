#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX36_CORE_INIT_SHA=c54728c08b220603790b8ebd2211114ab3ac343309ab6ba0f80d8d16bf4112e9
FIX35_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
FIX37_LIB64_SHA=fdc88b6bd7102ebcef0e172539fa85752f49077aef75eda8124c76175e96577c
FIX37_LIB32_SHA=0b466848ce61cc683407b7020815cb601b9b2111e4ab65ea987121fb0584692f
FIX38_HWB64_SHA=f3ffe369816dcd6ebc3c664980628089142ff39aa1a365abf9be63190d263a10
FIX38_HWB32_SHA=c2e3931ef763b8be78343f7b4931b85cec87c785066e81fe58c3561b44e7a997
ALLOC64_SHA=73c2ffc257e1e39825769fa66d8b53ff087c2e4de9e83c4778b44b61a7cef160
ALLOC32_SHA=914845eefb1f333044912f2ca49dcd9d08015e17de098e22afbe165476097549

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix39
VERIFY_MOUNT=/mnt/rgsp-system-fix39-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX39_BACKUP
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX39_SYSTEM_PREP.log

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

test "$(sha256sum "$SYSTEM_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX36_CORE_INIT_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX35_DEVICE_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB32_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libhidlbase.so" | awk '{print $1}')" = "$FIX38_HWB64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib/libhidlbase.so" | awk '{print $1}')" = "$FIX38_HWB32_SHA"

SRC64=$SYSTEM_MOUNT/system/lib64/android.hardware.graphics.allocator@2.0.so
SRC32=$SYSTEM_MOUNT/system/lib/android.hardware.graphics.allocator@2.0.so
DST64=$SYSTEM_MOUNT/system/vendor/lib64/android.hardware.graphics.allocator@2.0.so
DST32=$SYSTEM_MOUNT/system/vendor/lib/android.hardware.graphics.allocator@2.0.so
test "$(sha256sum "$SRC64" | awk '{print $1}')" = "$ALLOC64_SHA"
test "$(sha256sum "$SRC32" | awk '{print $1}')" = "$ALLOC32_SHA"
test ! -e "$DST64"
test ! -e "$DST32"

cp "$SRC64" "$BACKUP_DIR/android.hardware.graphics.allocator@2.0.so.64.source"
cp "$SRC32" "$BACKUP_DIR/android.hardware.graphics.allocator@2.0.so.32.source"
cp "$SRC64" "$DST64"
cp "$SRC32" "$DST32"
chown --reference="$SRC64" "$DST64"
chmod --reference="$SRC64" "$DST64"
chown --reference="$SRC32" "$DST32"
chmod --reference="$SRC32" "$DST32"

sync
POST_ALLOC64_SHA=$(sha256sum "$DST64" | awk '{print $1}')
POST_ALLOC32_SHA=$(sha256sum "$DST32" | awk '{print $1}')
test "$POST_ALLOC64_SHA" = "$ALLOC64_SHA"
test "$POST_ALLOC32_SHA" = "$ALLOC32_SHA"
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/lib64/android.hardware.graphics.allocator@2.0.so" | awk '{print $1}')" = "$ALLOC64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/lib/android.hardware.graphics.allocator@2.0.so" | awk '{print $1}')" = "$ALLOC32_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix39
  echo PATCH_SEMANTICS='Expose existing graphics allocator interface libraries in vendor sphal search paths'
  echo SOURCE64=system/lib64/android.hardware.graphics.allocator@2.0.so
  echo SOURCE32=system/lib/android.hardware.graphics.allocator@2.0.so
  echo TARGET64=system/vendor/lib64/android.hardware.graphics.allocator@2.0.so
  echo TARGET32=system/vendor/lib/android.hardware.graphics.allocator@2.0.so
  echo ALLOC64_SHA="$POST_ALLOC64_SHA"
  echo ALLOC32_SHA="$POST_ALLOC32_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
