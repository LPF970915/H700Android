#!/bin/sh
set -eu
TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX23_INIT_RC_SHA=58e4fade9fe9ed02f2f5d253e1c5240ed8932f51cf43888f4d278b769fe49999
FIX22_LMKD_RC_SHA=12ee33255d895c8706d24eb3eaaec520a27b1fce4969012373047da1c79353c2
FIX22_NETD_RC_SHA=ef0bd6803b6f4215041b2ec3ad1ffa54311d7d494e3e7afe896f22c2adef0bd5
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix24
VERIFY_MOUNT=/mnt/rgsp-system-fix24-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX24_BACKUP
test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"
mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT
test "$(sha256sum "$SYSTEM_MOUNT/init.sun50iw9p1.rc" | awk '{print $1}')" = "$FIX23_INIT_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/etc/init/lmkd.rc" | awk '{print $1}')" = "$FIX22_LMKD_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/etc/init/netd.rc" | awk '{print $1}')" = "$FIX22_NETD_RC_SHA"
link() {
  target=$1; name=$2
  if [ -L "$name" ]; then [ "$(readlink "$name")" = "$target" ] || exit 1; return; fi
  [ ! -e "$name" ] || { echo "unexpected existing file: $name" >&2; exit 1; }
  printf '%s -> %s\n' "$name" "$target" >> "$BACKUP_DIR/created-links"
  ln -s "$target" "$name"
}
link /apex/com.android.art.release/lib64/libandroidicu.so "$SYSTEM_MOUNT/system/lib64/libandroidicu.so"
link /apex/com.android.art.release/lib64/libnativebridge.so "$SYSTEM_MOUNT/system/lib64/libnativebridge.so"
link /apex/com.android.art.release/lib64/libnativehelper.so "$SYSTEM_MOUNT/system/lib64/libnativehelper.so"
link /apex/com.android.art.release/lib64/libnativeloader.so "$SYSTEM_MOUNT/system/lib64/libnativeloader.so"
link /apex/com.android.art.release/lib64/libdexfile_external.so "$SYSTEM_MOUNT/system/lib64/libdexfile_external.so"
link /apex/com.android.art.release/lib/libandroidicu.so "$SYSTEM_MOUNT/system/lib/libandroidicu.so"
link /apex/com.android.art.release/lib/libnativebridge.so "$SYSTEM_MOUNT/system/lib/libnativebridge.so"
link /apex/com.android.art.release/lib/libnativehelper.so "$SYSTEM_MOUNT/system/lib/libnativehelper.so"
link /apex/com.android.art.release/lib/libnativeloader.so "$SYSTEM_MOUNT/system/lib/libnativeloader.so"
link /apex/com.android.art.release/lib/libdexfile_external.so "$SYSTEM_MOUNT/system/lib/libdexfile_external.so"
link /apex/com.android.os.statsd/lib64/libstatssocket.so "$SYSTEM_MOUNT/system/lib64/libstatssocket.so"
link /apex/com.android.os.statsd/lib64/libstatspull.so "$SYSTEM_MOUNT/system/lib64/libstatspull.so"
link /apex/com.android.os.statsd/lib/libstatssocket.so "$SYSTEM_MOUNT/system/lib/libstatssocket.so"
link /apex/com.android.os.statsd/lib/libstatspull.so "$SYSTEM_MOUNT/system/lib/libstatspull.so"
link /apex/com.android.adbd/lib64/libadb_protos.so "$SYSTEM_MOUNT/system/lib64/libadb_protos.so"
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"
mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
for p in system/lib64/libandroidicu.so system/lib64/libnativeloader.so system/lib64/libstatssocket.so system/lib64/libstatspull.so system/lib64/libadb_protos.so system/lib/libandroidicu.so system/lib/libnativeloader.so system/lib/libstatssocket.so system/lib/libstatspull.so; do test -L "$VERIFY_MOUNT/$p"; done
umount "$VERIFY_MOUNT"
trap - EXIT
{ echo DATE=2026-08-29; echo FIX=fix24; echo PATCH_SEMANTICS='Expose critical flattened APEX libraries through legacy system lib search paths'; cat "$BACKUP_DIR/created-links"; echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"; echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"; } | tee /mnt/sdcard/RGSP_ANDROID_FIX24_SYSTEM_PREP.log
