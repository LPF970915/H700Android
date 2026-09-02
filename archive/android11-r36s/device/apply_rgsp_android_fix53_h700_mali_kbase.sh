#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX52_SYSTEM_PROP_SHA=d44083d504f4969ce612f8d1af550b4e98e1c8a94c1ad3be29977bde99398fb0
FIX52_VENDOR_PROP_SHA=b7434ae2d0b1af79bda100033075f20805e6e7bdedb702f45d5b001aa46e3c44
FIX52_UEVENT_RC_SHA=d67035ae852fd51e3dafd0386072ba4eac5350fa6102ef6602a5168c9d2ada3b
MALI_KBASE_SHA=987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9
COMPOSER22_BIN_SHA=151a9e533fee3c6301cd1bb794d35dad22e721764b3538cee22dda64be9cd22c
MAPPER32_SHA=7b7d1588c99b634d63690fb9b9219d936e11d538761e86b1ce37bfe875c3acdb
MAPPER64_SHA=dde77a1b7768dfc8ca2d69d710ef2f3c2f7daf594ab57f9dcfa001683111fd2b

PAYLOAD=/tmp/rgsp-fix53-payload
MANIFEST=/tmp/rgsp-fix53-payload.sha256
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix53
VERIFY_MOUNT=/mnt/rgsp-system-fix53-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX53_BACKUP
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX53_SYSTEM_PREP.log
MALI_RULE='/dev/mali0                  0666    system      graphics'

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test -d "$PAYLOAD/system"
test -f "$MANIFEST"
(cd "$PAYLOAD" && sha256sum -c "$MANIFEST")
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

SYSTEM_PROP=$SYSTEM_MOUNT/system/build.prop
VENDOR_PROP=$SYSTEM_MOUNT/system/vendor/build.prop
UEVENT_RC=$SYSTEM_MOUNT/system/etc/ueventd.rc
MODULE_TARGET=$SYSTEM_MOUNT/system/vendor/modules/mali_kbase.ko
INIT_TARGET=$SYSTEM_MOUNT/system/vendor/etc/init/rgsp-mali-kbase.rc

test "$(sha256sum "$SYSTEM_PROP" | awk '{print $1}')" = "$FIX52_SYSTEM_PROP_SHA"
test "$(sha256sum "$VENDOR_PROP" | awk '{print $1}')" = "$FIX52_VENDOR_PROP_SHA"
test "$(sha256sum "$UEVENT_RC" | awk '{print $1}')" = "$FIX52_UEVENT_RC_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/bin/hw/android.hardware.graphics.composer@2.2-service" | awk '{print $1}')" = "$COMPOSER22_BIN_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so" | awk '{print $1}')" = "$MAPPER32_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so" | awk '{print $1}')" = "$MAPPER64_SHA"
test ! -e "$MODULE_TARGET"
test ! -e "$INIT_TARGET"
test "$(grep -Fxc "$MALI_RULE" "$UEVENT_RC")" = 0
test ! -e "$SYSTEM_MOUNT/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled"
test -f "$SYSTEM_MOUNT/system/rgsp-disabled-init/fix52/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled"

cp "$UEVENT_RC" "$BACKUP_DIR/ueventd.rc.fix52"
test "$(sha256sum "$BACKUP_DIR/ueventd.rc.fix52" | awk '{print $1}')" = "$FIX52_UEVENT_RC_SHA"
install -D -o 0 -g 0 -m 0644 "$PAYLOAD/system/vendor/modules/mali_kbase.ko" "$MODULE_TARGET"
install -D -o 0 -g 0 -m 0644 "$PAYLOAD/system/vendor/etc/init/rgsp-mali-kbase.rc" "$INIT_TARGET"
cat >> "$UEVENT_RC" <<'EOF'

# RGSP fix53: H616 Android 10 Mali device permissions
/dev/mali0                  0666    system      graphics
EOF

(cd "$SYSTEM_MOUNT" && sha256sum -c "$MANIFEST")
test "$(sha256sum "$MODULE_TARGET" | awk '{print $1}')" = "$MALI_KBASE_SHA"
test "$(grep -Fxc "$MALI_RULE" "$UEVENT_RC")" = 1
UEVENT_RC_SHA=$(sha256sum "$UEVENT_RC" | awk '{print $1}')
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
(cd "$VERIFY_MOUNT" && sha256sum -c "$MANIFEST")
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/modules/mali_kbase.ko" | awk '{print $1}')" = "$MALI_KBASE_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/ueventd.rc" | awk '{print $1}')" = "$UEVENT_RC_SHA"
test "$(grep -Fxc "$MALI_RULE" "$VERIFY_MOUNT/system/etc/ueventd.rc")" = 1
test ! -e "$VERIFY_MOUNT/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-09-02
  echo FIX=fix53
  echo BASELINE='H616 Android 10; H618 not used'
  echo MODULE_SOURCE='RGSP H700 original Linux /usr/lib/modules/mali_kbase.ko'
  echo MODULE_SHA="$MALI_KBASE_SHA"
  echo UEVENT_RC_SHA="$UEVENT_RC_SHA"
  echo LOAD_TRIGGER=late-fs
} | tee "$PREP_LOG"
