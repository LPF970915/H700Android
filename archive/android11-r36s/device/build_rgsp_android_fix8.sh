#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/rgsp-fix8.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/tools/extract_ramdisk.py" \
  "$ROOT/out/rgsp-android-handoff-ramdisk-fix7.gz" \
  "$WORK/root"
cp "$ROOT/ramdisk/android-handoff-init" "$WORK/root/init"
chmod 0755 "$WORK/root/init"
sh -n "$WORK/root/init"

python3 "$ROOT/tools/make_ramdisk.py" \
  "$WORK/root" \
  "$ROOT/out/rgsp-android-handoff-ramdisk-fix8.gz"
python3 "$ROOT/tools/android_bootimg.py" pack \
  "$ROOT/out/rgsp-android11-handoff-boot-fix7.img" \
  "$ROOT/out/rgsp-android11-handoff-boot-fix8.img" \
  --ramdisk "$ROOT/out/rgsp-android-handoff-ramdisk-fix8.gz"

python3 "$ROOT/tools/extract_ramdisk.py" \
  "$ROOT/out/rgsp-android-handoff-ramdisk-fix8.gz" \
  "$WORK/verify"
cmp "$WORK/verify/init" "$ROOT/ramdisk/android-handoff-init"
test "$(stat -c '%a' "$WORK/verify/init")" = 755

printf 'BUILT_INIT_SHA='
sha256sum "$WORK/root/init" | cut -d' ' -f1
printf 'RAMDISK_SHA='
sha256sum "$ROOT/out/rgsp-android-handoff-ramdisk-fix8.gz" | cut -d' ' -f1
printf 'BOOT_SHA='
sha256sum "$ROOT/out/rgsp-android11-handoff-boot-fix8.img" | cut -d' ' -f1
printf 'VERIFIED_INIT_SHA='
sha256sum "$WORK/verify/init" | cut -d' ' -f1
