#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX19_BOOT_SHA=24d19ab2ce874c4150e84751f9fbec16cee74c6aa41e9906120f512341f547c6
FIX14_INIT_SHA=036017d5e42d4243e3f18bc014adfa71da224b5444cb0ee92cf578f4d36be5cd
FIX19_LIBSELINUX_SHA=bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984
FIX18_INIT_RC_SHA=f2038ef115b7d01e5bf5e2f9dc7a080eb6b4a272ded72e33847dc506d7defad9

BOOT_IMAGE=/mnt/roms/rgsp-android11-handoff-boot-fix19.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
VERIFY_MOUNT=/mnt/rgsp-fix19-verify

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')" = "$FIX19_BOOT_SHA"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
e2fsck -fn /dev/mmcblk1p2

mkdir -p "$VERIFY_MOUNT"
mount -t ext4 -o ro /dev/mmcblk1p2 "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test "$(sha256sum "$VERIFY_MOUNT/system/bin/init" | awk '{print $1}')" = "$FIX14_INIT_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX19_LIBSELINUX_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/etc/init/hw/init.rc" | awk '{print $1}')" = "$FIX18_INIT_RC_SHA"
grep -Fqx '    mount none /system/apex /apex bind rec' "$VERIFY_MOUNT/system/etc/init/hw/init.rc"
umount "$VERIFY_MOUNT"
trap - EXIT

rm -f "$MARKER" /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_STAGE_LAST.log /mnt/sdcard/RGSP_ANDROID_WATCH_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log /mnt/sdcard/RGSP_ANDROID_POWERCTL_LAST.log
dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$FIX19_BOOT_SHA"
printf 'fix19 one-shot 2026-08-28 init=%s libselinux=%s init_rc=%s boot=%s\n' \
  "$FIX14_INIT_SHA" "$FIX19_LIBSELINUX_SHA" "$FIX18_INIT_RC_SHA" "$FIX19_BOOT_SHA" > "$MARKER"
sync

{
  echo DATE=2026-08-28
  echo TF1_CID="$TF1_CID"
  echo TF2_CID="$TF2_CID"
  echo BOOT_WRITTEN_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
  echo SYSTEM_INIT_SHA="$FIX14_INIT_SHA"
  echo SYSTEM_LIBSELINUX_SHA="$FIX19_LIBSELINUX_SHA"
  echo SYSTEM_INIT_RC_SHA="$FIX18_INIT_RC_SHA"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX19_DEVICE_PREP.log
