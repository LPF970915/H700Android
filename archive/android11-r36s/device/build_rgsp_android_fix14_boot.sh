#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/rgsp-fix14-boot.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
python3 "$ROOT/tools/extract_ramdisk.py" "$ROOT/out/rgsp-android-handoff-ramdisk-fix13.gz" "$WORK/root"
cp "$ROOT/ramdisk/android-handoff-init" "$WORK/root/init"
chmod 0755 "$WORK/root/init"
sh -n "$WORK/root/init"
python3 "$ROOT/tools/make_ramdisk.py" "$WORK/root" "$ROOT/out/rgsp-android-handoff-ramdisk-fix14.gz"
python3 "$ROOT/tools/android_bootimg.py" pack \
  "$ROOT/out/rgsp-android11-handoff-boot-fix13.img" \
  "$ROOT/out/rgsp-android11-handoff-boot-fix14.img" \
  --ramdisk "$ROOT/out/rgsp-android-handoff-ramdisk-fix14.gz"
python3 "$ROOT/tools/extract_ramdisk.py" "$ROOT/out/rgsp-android-handoff-ramdisk-fix14.gz" "$WORK/verify"
cmp "$WORK/verify/init" "$ROOT/ramdisk/android-handoff-init"
test "$(stat -c '%a' "$WORK/verify/init")" = 755
sha256sum "$ROOT/out/rgsp-android-handoff-ramdisk-fix14.gz" "$ROOT/out/rgsp-android11-handoff-boot-fix14.img"
