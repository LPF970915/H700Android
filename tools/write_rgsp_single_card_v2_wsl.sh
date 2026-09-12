#!/bin/bash
set -euo pipefail
OUT=${1:?output directory}
DEV=${2:?whole disk device}
test -b "$DEV"
test "$(blockdev --getsize64 "$DEV")" = 62239277056
test -f "$OUT/prefix-212m.bin"
test -f "$OUT/boot.img"
test -f "$OUT/gpt-tail.bin"
test -f "$OUT/roms-metadata.bin"
test "$(stat -c %s "$OUT/prefix-212m.bin")" = 222298112
test "$(stat -c %s "$OUT/boot.img")" = 67108864
test "$(stat -c %s "$OUT/system.raw.img" 2>/dev/null || stat -c %s "/mnt/d/Works/H700Android/out/rgsp-single-card-20260911/system.raw.img")" = 8589934592
dd if="$OUT/prefix-212m.bin" of="$DEV" bs=4M conv=fsync status=progress
dd if="$OUT/boot.img" of="$DEV" bs=512 seek=303104 conv=fsync status=progress
dd if="/mnt/d/Works/H700Android/out/rgsp-single-card-20260911/system.raw.img" of="$DEV" bs=512 seek=434176 conv=fsync status=progress
dd if="/mnt/d/Works/H700Android/out/rgsp-single-card-20260911/vendor.raw.img" of="$DEV" bs=512 seek=17211392 conv=fsync status=progress
dd if="/mnt/d/Works/H700Android/out/rgsp-single-card-20260911/data.raw.img" of="$DEV" bs=512 seek=21118976 conv=fsync status=progress
dd if="$OUT/roms-metadata.bin" of="$DEV" bs=512 seek=54960128 conv=fsync status=progress
dd if="$OUT/gpt-tail.bin" of="$DEV" bs=512 seek=121561085 conv=fsync status=progress
sync
sha256sum "$OUT/prefix-212m.bin" "$OUT/boot.img" \
  /mnt/d/Works/H700Android/out/rgsp-single-card-20260911/system.raw.img \
  /mnt/d/Works/H700Android/out/rgsp-single-card-20260911/vendor.raw.img \
  /mnt/d/Works/H700Android/out/rgsp-single-card-20260911/data.raw.img
echo SINGLE_CARD_V2_WSL_WRITE_DONE
