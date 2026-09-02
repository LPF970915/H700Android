#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/rgsp-fix50-libselinux.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

aarch64-linux-gnu-as -o "$WORK/stubs.o" "$ROOT/work/fix50-libselinux-stubs.S"
aarch64-linux-gnu-ld -Ttext=0 \
  --defsym STR_FALSE=0x2f7b \
  --defsym STRDUP_PLT=0x15ad0 \
  -o "$WORK/stubs.elf" "$WORK/stubs.o"
aarch64-linux-gnu-objcopy -O binary --only-section=.text \
  "$WORK/stubs.elf" "$WORK/stubs.bin"

python3 "$ROOT/tools/patch_rgsp_android_fix50_libselinux.py" \
  "$ROOT/out/rgsp-android-libselinux-fix19.so" \
  "$WORK/stubs.bin" \
  "$ROOT/out/rgsp-android-libselinux-fix50.so"

aarch64-linux-gnu-objdump -d \
  --start-address=0x10918 --stop-address=0x10940 \
  "$ROOT/out/rgsp-android-libselinux-fix50.so"
aarch64-linux-gnu-readelf -Ws "$ROOT/out/rgsp-android-libselinux-fix50.so" |
  grep -E ' (lgetfilecon|getfilecon|selinux_status_open|selinux_status_updated)@@'
sha256sum "$ROOT/out/rgsp-android-libselinux-fix50.so"
