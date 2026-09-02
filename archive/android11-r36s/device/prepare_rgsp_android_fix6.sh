#!/bin/sh
set -eu

TF1_CID_EXPECTED=1d414455534400002000009f9401a1e7
TF2_CID_EXPECTED=fe3432534400000020000005bc01896b
ENV_SHA_EXPECTED=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
BOOT_SHA_EXPECTED=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix6
ANBOOT_MOUNT=/mnt/sdcard
BACKUP_DIR=$ANBOOT_MOUNT/RGSP_FIX6_BACKUP

fail() {
  echo "[fix6] ERROR: $*" >&2
  exit 1
}

[ "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5 ] || fail "unexpected root device"
[ "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID_EXPECTED" ] || fail "unexpected TF1 CID"
[ "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID_EXPECTED" ] || fail "unexpected TF2 CID"

ENV_SHA=$(dd if=/dev/mmcblk0p3 bs=131072 count=1 2>/dev/null | sha256sum | awk '{print $1}')
[ "$ENV_SHA" = "$ENV_SHA_EXPECTED" ] || fail "TF1 env hash mismatch: $ENV_SHA"
BOOT_SHA=$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')
[ "$BOOT_SHA" = "$BOOT_SHA_EXPECTED" ] || fail "TF1 boot is not the restored stock image: $BOOT_SHA"

for file in fstab.sun50iw9p1 ueventd.sun50iw9p1.rc init.sun50iw9p1.rc rgsp-boot-watch.sh; do
  [ -f "/tmp/$file" ] || fail "missing /tmp/$file"
done

mountpoint -q "$ANBOOT_MOUNT" || mount -t vfat -o rw /dev/mmcblk1p1 "$ANBOOT_MOUNT"
findmnt -n -S "$SYSTEM_DEV" >/dev/null 2>&1 && fail "$SYSTEM_DEV is already mounted"
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
cleanup() {
  mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true
}
trap cleanup EXIT INT TERM

for file in fstab.sun50iw9p1 ueventd.sun50iw9p1.rc init.sun50iw9p1.rc; do
  [ ! -e "$SYSTEM_MOUNT/$file" ] || cp -p "$SYSTEM_MOUNT/$file" "$BACKUP_DIR/$file.pre-fix6"
done
[ ! -e "$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh" ] || \
  cp -p "$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh" "$BACKUP_DIR/rgsp-boot-watch.sh.pre-fix6"

cp /tmp/fstab.sun50iw9p1 "$SYSTEM_MOUNT/fstab.sun50iw9p1"
cp /tmp/ueventd.sun50iw9p1.rc "$SYSTEM_MOUNT/ueventd.sun50iw9p1.rc"
cp /tmp/init.sun50iw9p1.rc "$SYSTEM_MOUNT/init.sun50iw9p1.rc"
cp /tmp/rgsp-boot-watch.sh "$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh"
chmod 0644 "$SYSTEM_MOUNT/fstab.sun50iw9p1" \
  "$SYSTEM_MOUNT/ueventd.sun50iw9p1.rc" \
  "$SYSTEM_MOUNT/init.sun50iw9p1.rc"
chmod 0755 "$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh"
sync

{
  echo "fix6 prepared $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "root=$(findmnt -n -o SOURCE /)"
  echo "tf1_cid=$(cat /sys/block/mmcblk0/device/cid)"
  echo "tf2_cid=$(cat /sys/block/mmcblk1/device/cid)"
  echo "env_head=$ENV_SHA"
  echo "tf1_boot=$BOOT_SHA"
  sha256sum \
    "$SYSTEM_MOUNT/fstab.sun50iw9p1" \
    "$SYSTEM_MOUNT/ueventd.sun50iw9p1.rc" \
    "$SYSTEM_MOUNT/init.sun50iw9p1.rc" \
    "$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh"
} | tee "$ANBOOT_MOUNT/RGSP_ANDROID_FIX6_PREP.log"

umount "$SYSTEM_MOUNT"
trap - EXIT INT TERM
e2fsck -fn "$SYSTEM_DEV"
sync
echo '[fix6] Android system instrumentation installed and verified'
