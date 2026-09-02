#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
PRE_FIX29_INIT_RC_SHA=f2038ef115b7d01e5bf5e2f9dc7a080eb6b4a272ded72e33847dc506d7defad9
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix29
VERIFY_MOUNT=/mnt/rgsp-system-fix29-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX29_BACKUP

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
TARGET=$SYSTEM_MOUNT/system/etc/init/hw/init.rc
test "$(sha256sum "$TARGET" | awk '{print $1}')" = "$PRE_FIX29_INIT_RC_SHA"
cp "$TARGET" "$BACKUP_DIR/init.rc.pre-fix29"

awk '
  /^    # Generate ld.config.txt for early executed processes$/ && !pre {
    print "    # Expose flattened APEX packages before linkerconfig scans /apex."
    print "    mount none /system/apex /apex bind rec"
    print ""
    pre=1
  }
  { print }
  /^    chmod 644 \/linkerconfig\/default\/ld.config.txt$/ && !bootstrap_log {
    print "    copy /linkerconfig/bootstrap/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_BOOTSTRAP_LAST.log"
    bootstrap_log=1
  }
  /^    update_linker_config$/ && !final_log {
    print "    copy /linkerconfig/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_LAST.log"
    final_log=1
  }
  END {
    if (!pre || !bootstrap_log || !final_log) exit 42
  }
' "$TARGET" > "$TARGET.fix29"
chown --reference="$TARGET" "$TARGET.fix29"
chmod --reference="$TARGET" "$TARGET.fix29"
mv "$TARGET.fix29" "$TARGET"

test "$(grep -Fxc '    mount none /system/apex /apex bind rec' "$TARGET")" = 2
grep -Fqx '    copy /linkerconfig/bootstrap/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_BOOTSTRAP_LAST.log' "$TARGET"
grep -Fqx '    copy /linkerconfig/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_LAST.log' "$TARGET"
sync
PATCHED_SHA=$(sha256sum "$TARGET" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
VERIFY_TARGET=$VERIFY_MOUNT/system/etc/init/hw/init.rc
test "$(sha256sum "$VERIFY_TARGET" | awk '{print $1}')" = "$PATCHED_SHA"
test "$(grep -Fxc '    mount none /system/apex /apex bind rec' "$VERIFY_TARGET")" = 2
grep -Fqx '    copy /linkerconfig/ld.config.txt /rgsp-persist/RGSP_ANDROID_LINKERCONFIG_LAST.log' "$VERIFY_TARGET"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix29
  echo PATCH_SEMANTICS='Expose flattened APEX before linkerconfig generation and persist both configs'
  echo PRE_INIT_RC_SHA="$PRE_FIX29_INIT_RC_SHA"
  echo POST_INIT_RC_SHA="$PATCHED_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX29_SYSTEM_PREP.log
