#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX36_CORE_INIT_SHA=c54728c08b220603790b8ebd2211114ab3ac343309ab6ba0f80d8d16bf4112e9
FIX36_DEVICE_RC_SHA=43c3041780be6f21514d02c3fa0566fcc4aff8ff8c1eab1ea5acf7e024d9ad93
LIB64_SHA=2240a87050986895868f73c96e7fe04b83eff26b3e6a0ad00c49d5dbbfe70f22
LIB32_SHA=3c66d0d94978052d2747f95aadf9528ae39238c2ec6d4a0dad0ac25439d8116b

SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix37
VERIFY_MOUNT=/mnt/rgsp-system-fix37-verify
BACKUP_DIR=/root/RGSP_FIX37_BACKUP
PREP_LOG=/root/RGSP_ANDROID_FIX37_SYSTEM_PREP.log

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

LIB64=$SYSTEM_MOUNT/system/lib64/libbinder.so
LIB32=$SYSTEM_MOUNT/system/lib/libbinder.so
CORE_INIT_RC=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
test "$(sha256sum "$CORE_INIT_RC" | awk '{print $1}')" = "$FIX36_CORE_INIT_SHA"
test "$(sha256sum "$LIB64" | awk '{print $1}')" = "$LIB64_SHA"
test "$(sha256sum "$LIB32" | awk '{print $1}')" = "$LIB32_SHA"

check_and_patch() {
  src=$1
  dst=$2
  ext=$3
  legacy=$4
  expected_ext=$5
  expected_legacy=$6
  dd if="$src" of=/tmp/rgsp-fix37-ext bs=1 skip="$ext" count=8 status=none
  dd if="$src" of=/tmp/rgsp-fix37-legacy bs=1 skip="$legacy" count=8 status=none
  test "$(od -An -tx1 /tmp/rgsp-fix37-ext | tr -d ' \n')" = "$expected_ext"
  test "$(od -An -tx1 /tmp/rgsp-fix37-legacy | tr -d ' \n')" = "$expected_legacy"
  cp -a "$src" "$dst"
  dd if=/tmp/rgsp-fix37-legacy of="$dst" bs=1 seek="$ext" count=8 conv=notrunc status=none
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
  dd if="$src" of=/tmp/rgsp-fix37-ext-lo bs=1 skip="$ext_lo" count=4 status=none
  dd if="$src" of=/tmp/rgsp-fix37-ext-hi bs=1 skip="$ext_hi" count=4 status=none
  dd if="$src" of=/tmp/rgsp-fix37-legacy-lo bs=1 skip="$legacy_lo" count=4 status=none
  dd if="$src" of=/tmp/rgsp-fix37-legacy-hi bs=1 skip="$legacy_hi" count=4 status=none
  test "$(od -An -tx1 /tmp/rgsp-fix37-ext-lo | tr -d ' \n')" = "$expected_ext_lo"
  test "$(od -An -tx1 /tmp/rgsp-fix37-ext-hi | tr -d ' \n')" = "$expected_ext_hi"
  test "$(od -An -tx1 /tmp/rgsp-fix37-legacy-lo | tr -d ' \n')" = "$expected_legacy_lo"
  test "$(od -An -tx1 /tmp/rgsp-fix37-legacy-hi | tr -d ' \n')" = "$expected_legacy_hi"
  cp -a "$src" "$dst"
  dd if=/tmp/rgsp-fix37-legacy-lo of="$dst" bs=1 seek="$ext_lo" count=4 conv=notrunc status=none
  dd if=/tmp/rgsp-fix37-legacy-hi of="$dst" bs=1 seek="$ext_hi" count=4 conv=notrunc status=none
}

cp "$LIB64" "$BACKUP_DIR/libbinder.so.64.pre-fix37"
cp "$LIB32" "$BACKUP_DIR/libbinder.so.32.pre-fix37"
check_and_patch "$LIB64" "$LIB64.fix37" $((0x759d4)) $((0x75a28)) \
  a1418c520103a872 e1408c528100a872
check_and_patch_thumb_immediates "$LIB32" "$LIB32.fix37" \
  $((0x5210a)) $((0x5210e)) $((0x5214a)) $((0x52152)) \
  46f20d21 c4f21801 46f20721 c4f20401
chown --reference="$LIB64" "$LIB64.fix37"; chmod --reference="$LIB64" "$LIB64.fix37"
chown --reference="$LIB32" "$LIB32.fix37"; chmod --reference="$LIB32" "$LIB32.fix37"
mv "$LIB64.fix37" "$LIB64"
mv "$LIB32.fix37" "$LIB32"

sync
POST_LIB64_SHA=$(sha256sum "$LIB64" | awk '{print $1}')
POST_LIB32_SHA=$(sha256sum "$LIB32" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libbinder.so" | awk '{print $1}')" = "$POST_LIB64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib/libbinder.so" | awk '{print $1}')" = "$POST_LIB32_SHA"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-30
  echo FIX=fix37
  echo PATCH_SEMANTICS='Force libbinder context-manager registration through legacy ioctl fallback'
  echo PRE_CORE_INIT_SHA="$FIX36_CORE_INIT_SHA"
  echo PRE_LIB64_SHA="$LIB64_SHA"
  echo PRE_LIB32_SHA="$LIB32_SHA"
  echo POST_LIB64_SHA="$POST_LIB64_SHA"
  echo POST_LIB32_SHA="$POST_LIB32_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
