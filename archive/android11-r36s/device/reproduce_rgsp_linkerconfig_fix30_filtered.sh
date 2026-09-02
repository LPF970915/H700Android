#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
SYSTEM_DEV=/dev/mmcblk1p2
ROOT=/mnt/rgsp-linkerconfig-fix30
OUT=/mnt/sdcard/RGSP_ANDROID_LINKERCONFIG_FIX30_REPRO.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20

mkdir -p "$ROOT"
mount -t ext4 -o ro "$SYSTEM_DEV" "$ROOT"
cleanup() {
  for mountpoint_path in "$ROOT"/apex/*; do
    mountpoint -q "$mountpoint_path" && umount "$mountpoint_path" || true
  done
  mountpoint -q "$ROOT/linkerconfig" && umount "$ROOT/linkerconfig" || true
  mountpoint -q "$ROOT/dev" && umount "$ROOT/dev" || true
  mountpoint -q "$ROOT/proc" && umount "$ROOT/proc" || true
  mountpoint -q "$ROOT/sys" && umount "$ROOT/sys" || true
  mountpoint -q "$ROOT/apex" && umount "$ROOT/apex" || true
  mountpoint -q "$ROOT" && umount "$ROOT" || true
}
trap cleanup EXIT

mount -t tmpfs -o mode=0755 tmpfs "$ROOT/apex"
for source in "$ROOT"/system/apex/*; do
  test -d "$source" || continue
  test -L "$source" && continue
  name=${source##*/}
  mkdir "$ROOT/apex/$name"
  mount -o bind "$source" "$ROOT/apex/$name"
done
mount -o bind /proc "$ROOT/proc"
mount -o bind /sys "$ROOT/sys"
mount -o bind /dev "$ROOT/dev"
mount -t tmpfs -o mode=0755 tmpfs "$ROOT/linkerconfig"

chroot "$ROOT" /system/bin/linkerconfig --target /linkerconfig
test -s "$ROOT/linkerconfig/ld.config.txt"
grep -Fq 'namespace.com_android_art.' "$ROOT/linkerconfig/ld.config.txt"
grep -Fq '/apex/com.android.art.release' "$ROOT/linkerconfig/ld.config.txt"

cp "$ROOT/linkerconfig/ld.config.txt" "$OUT"
sync
sha256sum "$OUT"
grep -n -E 'namespace\.com_android_art\.|/apex/com\.android\.art' "$OUT" | head -80
