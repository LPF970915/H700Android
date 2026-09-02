#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE="$ROOT/out/rgsp-android-libselinux-fix16.so"
OUTPUT="$ROOT/out/rgsp-android-libselinux-fix19.so"

python3 "$ROOT/tools/patch_rgsp_android_fix19_libselinux.py" \
  "$SOURCE" "$OUTPUT"

aarch64-linux-gnu-objdump -d \
  --start-address=0x11f08 --stop-address=0x11f10 "$OUTPUT"
aarch64-linux-gnu-objdump -d \
  --start-address=0x11fb0 --stop-address=0x11fb8 "$OUTPUT"

sha256sum "$SOURCE" "$OUTPUT"
