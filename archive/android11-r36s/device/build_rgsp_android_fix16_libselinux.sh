#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/rgsp-fix16-libselinux.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

aarch64-linux-gnu-as -o "$WORK/stubs.o" "$ROOT/work/fix16-libselinux-stubs.S"
aarch64-linux-gnu-ld -Ttext=0 \
  --defsym STR_NONE=0x2f21 \
  --defsym STR_FALSE=0x2f7b \
  --defsym STR_SELINUX=0x31ed \
  --defsym STRDUP_PLT=0x15ad0 \
  -o "$WORK/stubs.elf" "$WORK/stubs.o"
aarch64-linux-gnu-objcopy -O binary --only-section=.text \
  "$WORK/stubs.elf" "$WORK/stubs.bin"

python3 "$ROOT/tools/patch_rgsp_android_fix16_libselinux.py" \
  "$ROOT/out/rgsp-android-libselinux-fix11-current.so" \
  "$WORK/stubs.bin" \
  "$ROOT/out/rgsp-android-libselinux-fix16.so"

aarch64-linux-gnu-objdump -d \
  --start-address=0xe9b0 --stop-address=0xe9dc \
  "$ROOT/out/rgsp-android-libselinux-fix16.so"
aarch64-linux-gnu-objdump -d \
  --start-address=0xf390 --stop-address=0xf39c \
  "$ROOT/out/rgsp-android-libselinux-fix16.so"
aarch64-linux-gnu-objdump -d \
  --start-address=0xff38 --stop-address=0xff5c \
  "$ROOT/out/rgsp-android-libselinux-fix16.so"
aarch64-linux-gnu-objdump -d \
  --start-address=0x10350 --stop-address=0x10374 \
  "$ROOT/out/rgsp-android-libselinux-fix16.so"
aarch64-linux-gnu-objdump -d \
  --start-address=0x11770 --stop-address=0x11794 \
  "$ROOT/out/rgsp-android-libselinux-fix16.so"
sha256sum "$ROOT/out/rgsp-android-libselinux-fix16.so"
