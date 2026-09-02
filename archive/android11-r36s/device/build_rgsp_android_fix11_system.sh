#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SRC="$ROOT/out/rgsp-android11-alpha/rgsp-android11-system-alpha.img"
DST="$ROOT/out/rgsp-android11-system-alpha-fix11.img"
WORK=$(mktemp -d /tmp/rgsp-fix11.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

EXPECTED_SRC_SHA=793e4384f86c6c72a15ec6b60f4ac70701dc4218e189a6f5e7b929701e823f3f
actual_src_sha=$(sha256sum "$SRC" | awk '{print $1}')
test "$actual_src_sha" = "$EXPECTED_SRC_SHA" || {
  echo "refusing: unexpected source image hash $actual_src_sha" >&2
  exit 2
}

rm -f "$DST"
cp --reflink=auto "$SRC" "$DST"
debugfs -R "dump /system/lib64/libselinux.so $WORK/libselinux.so" "$DST" >/dev/null 2>&1
cp "$WORK/libselinux.so" "$WORK/libselinux.orig.so"

# AArch64: return NULL/0 from file-context handle, restorecon, and sethandle.
printf '\000\000\200\322\300\003\137\326' | dd of="$WORK/libselinux.so" bs=1 seek=$((0x12a38)) conv=notrunc status=none
printf '\000\000\200\122\300\003\137\326' | dd of="$WORK/libselinux.so" bs=1 seek=$((0x14748)) conv=notrunc status=none
printf '\300\003\137\326' | dd of="$WORK/libselinux.so" bs=1 seek=$((0x14fe0)) conv=notrunc status=none

debugfs -w -R "unlink /system/lib64/libselinux.so" "$DST" >/dev/null 2>&1
debugfs -w -R "write $WORK/libselinux.so /system/lib64/libselinux.so" "$DST" >/dev/null 2>&1
debugfs -R "dump /system/lib64/libselinux.so $WORK/libselinux.readback.so" "$DST" >/dev/null 2>&1
cmp "$WORK/libselinux.so" "$WORK/libselinux.readback.so"

set +e
e2fsck -fy "$DST" > "$ROOT/out/RGSP_ANDROID_FIX11_E2FSCK_REPAIR.log" 2>&1
repair_rc=$?
set -e
test "$repair_rc" -le 1 || {
  echo "e2fsck returned $repair_rc; inspect RGSP_ANDROID_FIX11_E2FSCK_REPAIR.log" >&2
  exit "$repair_rc"
}
e2fsck -fn "$DST" > "$ROOT/out/RGSP_ANDROID_FIX11_E2FSCK.log" 2>&1 || {
  rc=$?
  echo "final e2fsck returned $rc; inspect RGSP_ANDROID_FIX11_E2FSCK.log" >&2
  exit "$rc"
}

{
  echo "SOURCE=$SRC"
  echo "SOURCE_SHA256=$actual_src_sha"
  echo "OUTPUT=$DST"
  echo "OUTPUT_SHA256=$(sha256sum "$DST" | awk '{print $1}')"
  echo "LIBSELINUX_ORIGINAL_SHA256=$(sha256sum "$WORK/libselinux.orig.so" | awk '{print $1}')"
  echo "LIBSELINUX_PATCHED_SHA256=$(sha256sum "$WORK/libselinux.so" | awk '{print $1}')"
  echo "PATCH_OFFSETS=0x12a38,0x14748,0x14fe0"
  echo "E2FSCK_LOG=$ROOT/out/RGSP_ANDROID_FIX11_E2FSCK.log"
  echo "REAL_DEVICE_WRITTEN=no"
} | tee "$ROOT/out/RGSP_ANDROID_FIX11_PREP.log"
