#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX36_CORE_INIT_SHA=c54728c08b220603790b8ebd2211114ab3ac343309ab6ba0f80d8d16bf4112e9
FIX37_LIB64_SHA=fdc88b6bd7102ebcef0e172539fa85752f49077aef75eda8124c76175e96577c
FIX37_LIB32_SHA=0b466848ce61cc683407b7020815cb601b9b2111e4ab65ea987121fb0584692f
HWB64_SHA=bf697fca6dec8dec24fe7eaf1ad38cc66198bf6a5a24a27538f9d8cbe2582b7c
HWB32_SHA=d8c134961550a480af617080b53b23d28474a7050b78af9309434f094c93b6ea

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix38
VERIFY_MOUNT=/mnt/rgsp-system-fix38-verify
BACKUP_DIR=/root/RGSP_FIX38_BACKUP
PREP_LOG=/root/RGSP_ANDROID_FIX38_SYSTEM_PREP.log

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

LIB64=$SYSTEM_MOUNT/system/lib64/libhidlbase.so
LIB32=$SYSTEM_MOUNT/system/lib/libhidlbase.so
test "$(sha256sum "$SYSTEM_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX36_CORE_INIT_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib/libbinder.so" | awk '{print $1}')" = "$FIX37_LIB32_SHA"
test "$(sha256sum "$LIB64" | awk '{print $1}')" = "$HWB64_SHA"
test "$(sha256sum "$LIB32" | awk '{print $1}')" = "$HWB32_SHA"

check_and_patch() {
  src=$1
  dst=$2
  ext=$3
  legacy=$4
  expected_ext=$5
  expected_legacy=$6
  dd if="$src" of=/tmp/rgsp-fix38-ext bs=1 skip="$ext" count=8 status=none
  dd if="$src" of=/tmp/rgsp-fix38-legacy bs=1 skip="$legacy" count=8 status=none
  test "$(od -An -tx1 /tmp/rgsp-fix38-ext | tr -d ' \n')" = "$expected_ext"
  test "$(od -An -tx1 /tmp/rgsp-fix38-legacy | tr -d ' \n')" = "$expected_legacy"
  cp -a "$src" "$dst"
  dd if=/tmp/rgsp-fix38-legacy of="$dst" bs=1 seek="$ext" count=8 conv=notrunc status=none
}

check_and_patch_thumb_immediates() {
  src=$1
  dst=$2
  ext_lo=$3
  ext_hi=$4
  legacy_lo=$5
  legacy_hi=$6
  expected_ext_lo=$7
  expected_ext_hi=$8
  expected_legacy_lo=$9
  expected_legacy_hi=${10}
  dd if="$src" of=/tmp/rgsp-fix38-ext-lo bs=1 skip="$ext_lo" count=4 status=none
  dd if="$src" of=/tmp/rgsp-fix38-ext-hi bs=1 skip="$ext_hi" count=4 status=none
  dd if="$src" of=/tmp/rgsp-fix38-legacy-lo bs=1 skip="$legacy_lo" count=4 status=none
  dd if="$src" of=/tmp/rgsp-fix38-legacy-hi bs=1 skip="$legacy_hi" count=4 status=none
  test "$(od -An -tx1 /tmp/rgsp-fix38-ext-lo | tr -d ' \n')" = "$expected_ext_lo"
  test "$(od -An -tx1 /tmp/rgsp-fix38-ext-hi | tr -d ' \n')" = "$expected_ext_hi"
  test "$(od -An -tx1 /tmp/rgsp-fix38-legacy-lo | tr -d ' \n')" = "$expected_legacy_lo"
  test "$(od -An -tx1 /tmp/rgsp-fix38-legacy-hi | tr -d ' \n')" = "$expected_legacy_hi"
  cp -a "$src" "$dst"
  dd if=/tmp/rgsp-fix38-legacy-lo of="$dst" bs=1 seek="$ext_lo" count=4 conv=notrunc status=none
  dd if=/tmp/rgsp-fix38-legacy-hi of="$dst" bs=1 seek="$ext_hi" count=4 conv=notrunc status=none
}

cp "$LIB64" "$BACKUP_DIR/libhidlbase.so.64.pre-fix38"
cp "$LIB32" "$BACKUP_DIR/libhidlbase.so.32.pre-fix38"
check_and_patch "$LIB64" "$LIB64.fix38" $((0xa4ec8)) $((0xa4f1c)) \
  a1418c520103a872 e1408c528100a872
check_and_patch_thumb_immediates "$LIB32" "$LIB32.fix38" \
  $((0x7786c)) $((0x77870)) $((0x778ac)) $((0x778b4)) \
  46f20d21 c4f21801 46f20721 c4f20401
chown --reference="$LIB64" "$LIB64.fix38"; chmod --reference="$LIB64" "$LIB64.fix38"
chown --reference="$LIB32" "$LIB32.fix38"; chmod --reference="$LIB32" "$LIB32.fix38"
mv "$LIB64.fix38" "$LIB64"
mv "$LIB32.fix38" "$LIB32"

sync
POST_HWB64_SHA=$(sha256sum "$LIB64" | awk '{print $1}')
POST_HWB32_SHA=$(sha256sum "$LIB32" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libhidlbase.so" | awk '{print $1}')" = "$POST_HWB64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib/libhidlbase.so" | awk '{print $1}')" = "$POST_HWB32_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix38
  echo PATCH_SEMANTICS='Force libhidlbase hwbinder context-manager registration through legacy ioctl fallback'
  echo PRE_HWB64_SHA="$HWB64_SHA"
  echo PRE_HWB32_SHA="$HWB32_SHA"
  echo POST_HWB64_SHA="$POST_HWB64_SHA"
  echo POST_HWB32_SHA="$POST_HWB32_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
