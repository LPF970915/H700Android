#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix26
VERIFY_MOUNT=/mnt/rgsp-system-fix26-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX26_BACKUP
MANIFEST=$BACKUP_DIR/copied-art-libs.sha256

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
: > "$MANIFEST"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
COPIED_BYTES=0

for abi in lib64 lib; do
  for source in "$SYSTEM_MOUNT/system/apex/com.android.art.release/$abi/"*.so; do
    if [ -L "$source" ]; then
      continue
    fi
    test -f "$source"
    name=$(basename "$source")
    destination=$SYSTEM_MOUNT/system/$abi/$name
    expected=$(sha256sum "$source" | awk '{print $1}')
    size=$(stat -c %s "$source")
    if [ -e "$destination" ] || [ -L "$destination" ]; then
      if [ -f "$destination" ] && [ "$(sha256sum "$destination" | awk '{print $1}')" = "$expected" ]; then
        printf '%s %s %s\n' "$expected" "$abi" "$name" >> "$MANIFEST"
        COPIED_BYTES=$((COPIED_BYTES + size))
      fi
      continue
    fi
    cp "$source" "$destination.fix26"
    chown 0:0 "$destination.fix26"
    chmod 0644 "$destination.fix26"
    mv "$destination.fix26" "$destination"
    test "$(sha256sum "$destination" | awk '{print $1}')" = "$expected"
    printf '%s %s %s\n' "$expected" "$abi" "$name" >> "$MANIFEST"
    COPIED_BYTES=$((COPIED_BYTES + size))
  done
done

test -s "$MANIFEST"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
while read -r expected abi name; do
  test -f "$VERIFY_MOUNT/system/$abi/$name"
  test ! -L "$VERIFY_MOUNT/system/$abi/$name"
  test "$(sha256sum "$VERIFY_MOUNT/system/$abi/$name" | awk '{print $1}')" = "$expected"
done < "$MANIFEST"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix26
  echo PATCH_SEMANTICS='Copy the missing ART APEX shared-library closure without overwriting system libraries'
  echo COPIED_COUNT="$(wc -l < "$MANIFEST")"
  echo COPIED_BYTES="$COPIED_BYTES"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX26_SYSTEM_PREP.log
