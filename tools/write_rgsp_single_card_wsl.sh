#!/bin/bash
set -euo pipefail

OUT=${1:?staging directory required}
EXPECTED_BYTES=${2:?expected disk size required}
export OUT EXPECTED_BYTES

mapfile -t CANDIDATES < <(
  lsblk -bndo NAME,SIZE,TYPE |
    awk -v expected="$EXPECTED_BYTES" '$2 == expected && $3 == "disk" {print $1}'
)
if [ "${#CANDIDATES[@]}" -ne 1 ]; then
  printf 'Expected one matching whole disk, found %s\n' "${#CANDIDATES[@]}" >&2
  lsblk -o NAME,SIZE,TYPE,MODEL,SERIAL,TRAN >&2
  exit 20
fi
DEV="/dev/${CANDIDATES[0]}"

test -f "$OUT/boot-single-card.img"
test -f "$OUT/system.raw.img"
test -f "$OUT/vendor.raw.img"
test -f "$OUT/data.raw.img"
test "$(stat -c '%s' "$OUT/boot-single-card.img")" -eq 67108864
test "$(stat -c '%s' "$OUT/system.raw.img")" -eq 8589934592
test "$(stat -c '%s' "$OUT/vendor.raw.img")" -eq 2147483648
test "$(stat -c '%s' "$OUT/data.raw.img")" -eq 17179869184

sgdisk --zap-all "$DEV"
sgdisk \
  --new=1:2048:+64M --typecode=1:8300 --change-name=1:boot \
  --partition-guid=1:3b9b1a40-0d34-4b3d-9f53-1f4a1ad1c701 \
  --new=2:0:+8G --typecode=2:8300 --change-name=2:system \
  --partition-guid=2:096d7fa1-62e8-c242-9876-cfdd5a92b8eb \
  --new=3:0:+2G --typecode=3:8300 --change-name=3:vendor \
  --partition-guid=3:6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8 \
  --new=4:0:+16G --typecode=4:8300 --change-name=4:data \
  --partition-guid=4:734716ed-e7d9-e74f-9b3e-4f1cb8d448ed \
  --new=5:0:0 --typecode=5:0700 --change-name=5:ROMS \
  --partition-guid=5:b4d04d65-2c35-4b7f-b9c5-8f24d2f10505 \
  "$DEV"
sgdisk --verify "$DEV"
partprobe "$DEV"
sleep 2

for n in 1 2 3 4 5; do
  test -b "${DEV}${n}"
done

mkfs.ext4 -F -L ANDROID_DATA "${DEV}4"
mkfs.vfat -F 32 -n ROMS "${DEV}5"
dd if="$OUT/boot-single-card.img" of="${DEV}1" bs=4M conv=fsync status=progress
dd if="$OUT/system.raw.img" of="${DEV}2" bs=4M conv=fsync status=progress
dd if="$OUT/vendor.raw.img" of="${DEV}3" bs=4M conv=fsync status=progress
dd if="$OUT/data.raw.img" of="${DEV}4" bs=4M conv=fsync status=progress
sync

sha256sum \
  "$OUT/boot-single-card.img" \
  "$OUT/system.raw.img" \
  "$OUT/vendor.raw.img" \
  "$OUT/data.raw.img"
sha256sum "${DEV}1" "${DEV}2" "${DEV}3" "${DEV}4"
sgdisk --verify "$DEV"
fatlabel "${DEV}5"
blkid "${DEV}2" "${DEV}3" "${DEV}4" "${DEV}5"
