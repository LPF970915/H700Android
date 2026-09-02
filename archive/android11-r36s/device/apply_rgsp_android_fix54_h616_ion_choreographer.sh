#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX53_FRAMEWORK_SHA=95ce2d7b8b27d60adf9795fc29ea84e6cdb6226d200b7e94ce182a4fd3623177
FIX54_FRAMEWORK_SHA=a8076efd6d57c8b6a0c31d60ff6a518fa7b63aa4de9992bcca3b93af3e16a851
FIX53_UEVENT_RC_SHA=e76e011940bdbfa5e489a7bd6c4323456a8f3a861079811194046ec4129af1a2
FIX49_SERVICES_SHA=5b4ded60538f0a0a4903b56933eaa9527b11585028d9d9fc1e483fe52f8d3ce1
MALI_KBASE_SHA=987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9

PAYLOAD=/tmp/rgsp-fix54-payload
MANIFEST=/tmp/rgsp-fix54-payload.sha256
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix54
VERIFY_MOUNT=/mnt/rgsp-system-fix54-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX54_BACKUP
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX54_SYSTEM_PREP.log
ION_RULE='/dev/ion                    0777    system      graphics'
MALI_RULE='/dev/mali0                  0666    system      graphics'

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test -d "$PAYLOAD/system"
test -f "$MANIFEST"
(cd "$PAYLOAD" && sha256sum -c "$MANIFEST")
test "$(sha256sum "$PAYLOAD/system/framework/framework.jar" | awk '{print $1}')" = "$FIX54_FRAMEWORK_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

FRAMEWORK_JAR=$SYSTEM_MOUNT/system/framework/framework.jar
SERVICES_JAR=$SYSTEM_MOUNT/system/framework/services.jar
UEVENT_RC=$SYSTEM_MOUNT/system/etc/ueventd.rc
MALI_MODULE=$SYSTEM_MOUNT/system/vendor/modules/mali_kbase.ko

FRAMEWORK_SHA=$(sha256sum "$FRAMEWORK_JAR" | awk '{print $1}')
UEVENT_RC_SHA=$(sha256sum "$UEVENT_RC" | awk '{print $1}')
test "$FRAMEWORK_SHA" = "$FIX53_FRAMEWORK_SHA" || test "$FRAMEWORK_SHA" = "$FIX54_FRAMEWORK_SHA"
test "$UEVENT_RC_SHA" = "$FIX53_UEVENT_RC_SHA" || test "$(grep -Fxc "$ION_RULE" "$UEVENT_RC")" = 1
test "$(sha256sum "$SERVICES_JAR" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$MALI_MODULE" | awk '{print $1}')" = "$MALI_KBASE_SHA"
test "$(grep -Fxc "$MALI_RULE" "$UEVENT_RC")" = 1
test "$(grep -Fxc "$ION_RULE" "$UEVENT_RC")" -le 1

if test "$FRAMEWORK_SHA" = "$FIX53_FRAMEWORK_SHA"; then
  cp "$FRAMEWORK_JAR" "$BACKUP_DIR/framework.jar.fix53"
  test "$(sha256sum "$BACKUP_DIR/framework.jar.fix53" | awk '{print $1}')" = "$FIX53_FRAMEWORK_SHA"
  install -o 0 -g 0 -m 0644 "$PAYLOAD/system/framework/framework.jar" "$FRAMEWORK_JAR"
fi

if ! grep -Fqx "$ION_RULE" "$UEVENT_RC"; then
  cp "$UEVENT_RC" "$BACKUP_DIR/ueventd.rc.fix53"
  test "$(sha256sum "$BACKUP_DIR/ueventd.rc.fix53" | awk '{print $1}')" = "$FIX53_UEVENT_RC_SHA"
  cat >> "$UEVENT_RC" <<'EOF'

# RGSP fix54: H616 Android 10 ION device permissions
/dev/ion                    0777    system      graphics
EOF
fi

test "$(sha256sum "$FRAMEWORK_JAR" | awk '{print $1}')" = "$FIX54_FRAMEWORK_SHA"
test "$(grep -Fxc "$ION_RULE" "$UEVENT_RC")" = 1
test "$(grep -Fxc "$MALI_RULE" "$UEVENT_RC")" = 1
UEVENT_RC_SHA=$(sha256sum "$UEVENT_RC" | awk '{print $1}')
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
(cd "$VERIFY_MOUNT" && sha256sum -c "$MANIFEST")
test "$(sha256sum "$VERIFY_MOUNT/system/framework/framework.jar" | awk '{print $1}')" = "$FIX54_FRAMEWORK_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/modules/mali_kbase.ko" | awk '{print $1}')" = "$MALI_KBASE_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/ueventd.rc" | awk '{print $1}')" = "$UEVENT_RC_SHA"
test "$(grep -Fxc "$ION_RULE" "$VERIFY_MOUNT/system/etc/ueventd.rc")" = 1
test "$(grep -Fxc "$MALI_RULE" "$VERIFY_MOUNT/system/etc/ueventd.rc")" = 1
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo BUILD_DATE=2026-09-01
  echo DEVICE_DATE="$(date -Iseconds)"
  echo FIX=fix54
  echo BASELINE='H616 Android 10; H618 not used'
  echo PATCH_SEMANTICS='Use H616 ION permissions and tolerate DisplayManager startup ordering at 60 Hz'
  echo FRAMEWORK_JAR_SHA="$FIX54_FRAMEWORK_SHA"
  echo UEVENT_RC_SHA="$UEVENT_RC_SHA"
  echo MALI_MODULE_SHA="$MALI_KBASE_SHA"
} | tee "$PREP_LOG"
