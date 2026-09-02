#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d /tmp/rgsp-fix32-boot.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/tools/extract_ramdisk.py" "$ROOT/out/rgsp-android-handoff-ramdisk-fix31.gz" "$WORK/root"
sed -i 's/^HANDOFF_VERSION=fix31$/HANDOFF_VERSION=fix32/' "$WORK/root/init"
grep -Fqx 'HANDOFF_VERSION=fix32' "$WORK/root/init"
chmod 0755 "$WORK/root/init"
sh -n "$WORK/root/init"

python3 "$ROOT/tools/make_ramdisk.py" "$WORK/root" "$ROOT/out/rgsp-android-handoff-ramdisk-fix32.gz"
python3 "$ROOT/tools/android_bootimg.py" pack "$ROOT/out/rgsp-android11-handoff-boot-fix31.img" "$ROOT/out/rgsp-android11-handoff-boot-fix32.img" --ramdisk "$ROOT/out/rgsp-android-handoff-ramdisk-fix32.gz"
python3 "$ROOT/tools/extract_ramdisk.py" "$ROOT/out/rgsp-android-handoff-ramdisk-fix32.gz" "$WORK/verify"
cmp "$WORK/verify/init" "$WORK/root/init"
test "$(stat -c '%a' "$WORK/verify/init")" = 755
sha256sum "$ROOT/out/rgsp-android-handoff-ramdisk-fix32.gz" "$ROOT/out/rgsp-android11-handoff-boot-fix32.img"
