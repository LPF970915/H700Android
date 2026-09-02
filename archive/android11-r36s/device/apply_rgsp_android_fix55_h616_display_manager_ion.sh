#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX49_SERVICES_SHA=5b4ded60538f0a0a4903b56933eaa9527b11585028d9d9fc1e483fe52f8d3ce1
FIX55_SERVICES_SHA=4bfbedb901dff9634bc6b1e37bc9b1754b8188618a7f354c256727eaf907746e
FIX54_FRAMEWORK_SHA=a8076efd6d57c8b6a0c31d60ff6a518fa7b63aa4de9992bcca3b93af3e16a851
FIX53_FRAMEWORK_SHA=95ce2d7b8b27d60adf9795fc29ea84e6cdb6226d200b7e94ce182a4fd3623177
FIX54_SYSTEM_UEVENT_SHA=84447621b17a9771fb8e7f06264ec3531dcab0efc01722c5f71d64c40d50f24b
FIX53_SYSTEM_UEVENT_SHA=e76e011940bdbfa5e489a7bd6c4323456a8f3a861079811194046ec4129af1a2
FIX54_ROOT_UEVENT_SHA=34b8de3544d1c81a5d776f164d29e4e4c050e65bccb4e09b593e310e97027098
FIX55_ROOT_UEVENT_SHA=931c04f1809b633eb1298b929e76b6e4ab2114d32bc8d62ec690844f656743f6
FIX54_WATCH_SHA=b7264e878a3a9ee2c0a2d69b8010387803b44c95366260d91971929dc3fdecf1
FIX55_WATCH_SHA=61075666c4ed778e878c2a843ebd696d0754c76a0914170f5c3aaba4d6c7c00d

PAYLOAD=/tmp/rgsp-fix55-payload
MANIFEST=/tmp/rgsp-fix55-payload.sha256
SYSTEM_DEV=/dev/mmcblk1p2
DATA_DEV=/dev/mmcblk1p4
SYSTEM_MOUNT=/mnt/rgsp-system-fix55
VERIFY_MOUNT=/mnt/rgsp-system-fix55-verify
DATA_MOUNT=/mnt/rgsp-data-fix55
BACKUP_DIR=/mnt/sdcard/RGSP_FIX55_BACKUP
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX55_SYSTEM_PREP.log
ION_RULE='/dev/ion                 0777   system     graphics'

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test -d "$PAYLOAD/system"
test -f "$MANIFEST"
(cd "$PAYLOAD" && sha256sum -c "$MANIFEST")
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
findmnt -rn -S "$DATA_DEV" >/dev/null 2>&1 && exit 21
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$DATA_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

SERVICES_JAR=$SYSTEM_MOUNT/system/framework/services.jar
FRAMEWORK_JAR=$SYSTEM_MOUNT/system/framework/framework.jar
SYSTEM_UEVENT=$SYSTEM_MOUNT/system/etc/ueventd.rc
ROOT_UEVENT=$SYSTEM_MOUNT/ueventd.sun50iw9p1.rc
WATCH=$SYSTEM_MOUNT/system/bin/rgsp-boot-watch.sh

SERVICES_SHA=$(sha256sum "$SERVICES_JAR" | awk '{print $1}')
FRAMEWORK_SHA=$(sha256sum "$FRAMEWORK_JAR" | awk '{print $1}')
SYSTEM_UEVENT_SHA=$(sha256sum "$SYSTEM_UEVENT" | awk '{print $1}')
ROOT_UEVENT_SHA=$(sha256sum "$ROOT_UEVENT" | awk '{print $1}')
WATCH_SHA=$(sha256sum "$WATCH" | awk '{print $1}')

test "$SERVICES_SHA" = "$FIX49_SERVICES_SHA" || test "$SERVICES_SHA" = "$FIX55_SERVICES_SHA"
test "$FRAMEWORK_SHA" = "$FIX54_FRAMEWORK_SHA" || test "$FRAMEWORK_SHA" = "$FIX53_FRAMEWORK_SHA"
test "$SYSTEM_UEVENT_SHA" = "$FIX54_SYSTEM_UEVENT_SHA" || test "$SYSTEM_UEVENT_SHA" = "$FIX53_SYSTEM_UEVENT_SHA"
test "$ROOT_UEVENT_SHA" = "$FIX54_ROOT_UEVENT_SHA" || test "$ROOT_UEVENT_SHA" = "$FIX55_ROOT_UEVENT_SHA"
test "$WATCH_SHA" = "$FIX54_WATCH_SHA" || test "$WATCH_SHA" = "$FIX55_WATCH_SHA"

if test "$SERVICES_SHA" = "$FIX49_SERVICES_SHA"; then
  cp "$SERVICES_JAR" "$BACKUP_DIR/services.jar.fix49"
  test "$(sha256sum "$BACKUP_DIR/services.jar.fix49" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
fi
if test "$FRAMEWORK_SHA" = "$FIX54_FRAMEWORK_SHA"; then
  cp "$FRAMEWORK_JAR" "$BACKUP_DIR/framework.jar.fix54"
  test "$(sha256sum "$BACKUP_DIR/framework.jar.fix54" | awk '{print $1}')" = "$FIX54_FRAMEWORK_SHA"
fi
if test "$SYSTEM_UEVENT_SHA" = "$FIX54_SYSTEM_UEVENT_SHA"; then
  cp "$SYSTEM_UEVENT" "$BACKUP_DIR/ueventd.rc.fix54"
  test "$(sha256sum "$BACKUP_DIR/ueventd.rc.fix54" | awk '{print $1}')" = "$FIX54_SYSTEM_UEVENT_SHA"
fi
if test "$ROOT_UEVENT_SHA" = "$FIX54_ROOT_UEVENT_SHA"; then
  cp "$ROOT_UEVENT" "$BACKUP_DIR/ueventd.sun50iw9p1.rc.fix54"
  test "$(sha256sum "$BACKUP_DIR/ueventd.sun50iw9p1.rc.fix54" | awk '{print $1}')" = "$FIX54_ROOT_UEVENT_SHA"
fi
if test "$WATCH_SHA" = "$FIX54_WATCH_SHA"; then
  cp "$WATCH" "$BACKUP_DIR/rgsp-boot-watch.sh.fix54"
  test "$(sha256sum "$BACKUP_DIR/rgsp-boot-watch.sh.fix54" | awk '{print $1}')" = "$FIX54_WATCH_SHA"
fi

install -o 0 -g 0 -m 0644 "$PAYLOAD/system/framework/services.jar" "$SERVICES_JAR"
install -o 0 -g 0 -m 0644 "$PAYLOAD/system/framework/framework.jar" "$FRAMEWORK_JAR"
install -o 0 -g 0 -m 0644 "$PAYLOAD/system/etc/ueventd.rc" "$SYSTEM_UEVENT"
install -o 0 -g 0 -m 0644 "$PAYLOAD/ueventd.sun50iw9p1.rc" "$ROOT_UEVENT"
install -o 0 -g 0 -m 0755 "$PAYLOAD/system/bin/rgsp-boot-watch.sh" "$WATCH"

test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$FIX55_SERVICES_SHA"
test "$(sha256sum "$FRAMEWORK_JAR" | awk '{print $1}')" = "$FIX53_FRAMEWORK_SHA"
test "$(sha256sum "$SYSTEM_UEVENT" | awk '{print $1}')" = "$FIX53_SYSTEM_UEVENT_SHA"
test "$(sha256sum "$ROOT_UEVENT" | awk '{print $1}')" = "$FIX55_ROOT_UEVENT_SHA"
test "$(sha256sum "$WATCH" | awk '{print $1}')" = "$FIX55_WATCH_SHA"
test "$(grep -Fxc "$ION_RULE" "$ROOT_UEVENT")" = 1
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

set +e
e2fsck -p "$DATA_DEV"
DATA_FSCK_RC=$?
set -e
case "$DATA_FSCK_RC" in
  0|1) ;;
  *) exit "$DATA_FSCK_RC" ;;
esac

mount -t ext4 -o rw "$DATA_DEV" "$DATA_MOUNT"
trap 'mountpoint -q "$DATA_MOUNT" && umount "$DATA_MOUNT" || true' EXIT
DALVIK_DIR=$DATA_MOUNT/dalvik-cache/arm64
rm -f \
  "$DALVIK_DIR/system@framework@services.jar@classes.dex" \
  "$DALVIK_DIR/system@framework@services.jar@classes.vdex"
sync
umount "$DATA_MOUNT"
trap - EXIT
e2fsck -fn "$DATA_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
(cd "$VERIFY_MOUNT" && sha256sum -c "$MANIFEST")
test "$(grep -Fxc "$ION_RULE" "$VERIFY_MOUNT/ueventd.sun50iw9p1.rc")" = 1
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo BUILD_DATE=2026-09-02
  echo DEVICE_DATE="$(date -Iseconds)"
  echo FIX=fix55
  echo BASELINE='H616 Android 10; H618 not used'
  echo PATCH_SEMANTICS='Restore DisplayManagerService after fix44 headless diagnostics; apply H616 ION mode to the parsed root ueventd file'
  echo SERVICES_JAR_SHA="$FIX55_SERVICES_SHA"
  echo FRAMEWORK_JAR_SHA="$FIX53_FRAMEWORK_SHA"
  echo ROOT_UEVENT_SHA="$FIX55_ROOT_UEVENT_SHA"
  echo WATCH_SHA="$FIX55_WATCH_SHA"
  echo DATA_FSCK_RC="$DATA_FSCK_RC"
  echo SERVICES_DALVIK_CACHE_INVALIDATED=1
} | tee "$PREP_LOG"
