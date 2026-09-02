#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/rgsp-fix17-boot.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/tools/extract_ramdisk.py" \
  "$ROOT/out/rgsp-android-handoff-ramdisk-fix16.gz" "$WORK/root"
cp "$ROOT/ramdisk/android-handoff-init" "$WORK/root/init"
chmod 0755 "$WORK/root/init"
sh -n "$WORK/root/init"
grep -Fqx 'HANDOFF_VERSION=fix17' "$WORK/root/init"
grep -Fq 'mount -o bind /android-root/system/apex /android-root/apex' "$WORK/root/init"
python3 "$ROOT/tools/make_ramdisk.py" \
  "$WORK/root" "$ROOT/out/rgsp-android-handoff-ramdisk-fix17.gz"
python3 "$ROOT/tools/android_bootimg.py" pack \
  "$ROOT/out/rgsp-android11-handoff-boot-fix16.img" \
  "$ROOT/out/rgsp-android11-handoff-boot-fix17.img" \
  --ramdisk "$ROOT/out/rgsp-android-handoff-ramdisk-fix17.gz"
python3 "$ROOT/tools/extract_ramdisk.py" \
  "$ROOT/out/rgsp-android-handoff-ramdisk-fix17.gz" "$WORK/verify"
cmp "$WORK/verify/init" "$ROOT/ramdisk/android-handoff-init"
test "$(stat -c '%a' "$WORK/verify/init")" = 755
sha256sum "$ROOT/out/rgsp-android-handoff-ramdisk-fix17.gz" \
  "$ROOT/out/rgsp-android11-handoff-boot-fix17.img"
