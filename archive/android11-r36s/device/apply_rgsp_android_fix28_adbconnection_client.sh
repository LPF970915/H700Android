#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
ADB32_SHA=f0fdb1007a2cfd65107730b2b851316f80353a3709adc038d2bbdbc737fe6d97
ADB64_SHA=598a81a982950c4ec9d3f2e5b289aaf8e80d2d483c308b8475a4bc574ebe4b34
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix28
VERIFY_MOUNT=/mnt/rgsp-system-fix28-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX28_BACKUP
MANIFEST=$BACKUP_DIR/copied-adbconnection-client.sha256

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

for spec in "lib:$ADB32_SHA" "lib64:$ADB64_SHA"; do
  abi=${spec%%:*}
  expected=${spec#*:}
  source=$SYSTEM_MOUNT/system/apex/com.android.adbd/$abi/libadbconnection_client.so
  destination=$SYSTEM_MOUNT/system/$abi/libadbconnection_client.so
  test -f "$source"
  test ! -L "$source"
  test "$(sha256sum "$source" | awk '{print $1}')" = "$expected"
  if [ -e "$destination" ] || [ -L "$destination" ]; then
    test -f "$destination"
    test ! -L "$destination"
    test "$(sha256sum "$destination" | awk '{print $1}')" = "$expected"
  else
    cp "$source" "$destination.fix28"
    chown 0:0 "$destination.fix28"
    chmod 0644 "$destination.fix28"
    mv "$destination.fix28" "$destination"
  fi
  test "$(sha256sum "$destination" | awk '{print $1}')" = "$expected"
  printf '%s %s %s\n' "$expected" "$abi" libadbconnection_client.so >> "$MANIFEST"
done

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
  echo FIX=fix28
  echo PATCH_SEMANTICS='Copy the adbd APEX client library needed by both zygotes'
  cat "$MANIFEST"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX28_SYSTEM_PREP.log
