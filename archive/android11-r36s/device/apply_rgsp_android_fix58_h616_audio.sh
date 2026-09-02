#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
PAYLOAD=/tmp/rgsp-fix58-payload
MANIFEST=/tmp/rgsp-fix58-payload/PAYLOAD.sha256
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix58
VERIFY_MOUNT=/mnt/rgsp-system-fix58-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX58_BACKUP
PREP_LOG=/mnt/sdcard/RGSP_ANDROID_FIX58_SYSTEM_PREP.log

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test -f "$MANIFEST"
(cd "$PAYLOAD" && sha256sum -c "$MANIFEST")
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

backup_existing() {
  rel=$1
  src="$SYSTEM_MOUNT/$rel"
  [ -e "$src" ] || return 0
  dst="$BACKUP_DIR/$rel"
  mkdir -p "$(dirname "$dst")"
  # /mnt/sdcard does not preserve Unix ownership; content is sufficient here.
  cp -f "$src" "$dst"
}

install_payload() {
  mode=$1
  rel=$2
  install -D -o 0 -g 0 -m "$mode" "$PAYLOAD/$rel" "$SYSTEM_MOUNT/$rel"
}

for rel in \
  system/vendor/bin/hw/android.hardware.audio@2.0-service \
  system/vendor/lib/hw/android.hardware.audio@5.0-impl.so \
  system/vendor/lib/hw/android.hardware.audio.effect@5.0-impl.so \
  system/vendor/lib/hw/audio.primary.cupid.so \
  system/vendor/lib/hw/audio.primary.rk3326.so \
  system/vendor/lib/hw/audio.primary.default.so \
  system/vendor/lib/libtinyalsa_audio.so \
  system/vendor/lib/libwebrtc_audio_preprocessing.so \
  system/vendor/lib/soundfx/libaudiopreprocessing.so \
  system/vendor/lib/android.hardware.audio.common-util.so \
  system/vendor/lib/android.hardware.audio.common@5.0-util.so \
  system/vendor/etc/vintf/manifest.xml \
  system/vendor/etc/audio_policy_configuration.xml \
  system/vendor/etc/audio/audio_policy_configuration.xml \
  system/vendor/etc/audio_platform_info.xml \
  system/vendor/etc/audio_mixer_paths.xml \
  system/vendor/etc/audio_effects.xml \
  system/vendor/etc/init/android.hardware.audio@2.0-service.rc; do
  backup_existing "$rel"
done

for rel in \
  system/vendor/bin/hw/android.hardware.audio@2.0-service \
  system/vendor/lib/hw/android.hardware.audio@5.0-impl.so \
  system/vendor/lib/hw/android.hardware.audio.effect@5.0-impl.so \
  system/vendor/lib/hw/audio.primary.cupid.so \
  system/vendor/lib/hw/audio.primary.rk3326.so \
  system/vendor/lib/hw/audio.primary.default.so \
  system/vendor/lib/libtinyalsa_audio.so \
  system/vendor/lib/libwebrtc_audio_preprocessing.so \
  system/vendor/lib/soundfx/libaudiopreprocessing.so \
  system/vendor/lib/android.hardware.audio.common-util.so \
  system/vendor/lib/android.hardware.audio.common@5.0-util.so \
  system/vendor/etc/vintf/manifest.xml \
  system/vendor/etc/audio_policy_configuration.xml \
  system/vendor/etc/audio/audio_policy_configuration.xml \
  system/vendor/etc/audio_platform_info.xml \
  system/vendor/etc/audio_mixer_paths.xml \
  system/vendor/etc/audio_effects.xml \
  system/vendor/etc/init/android.hardware.audio@2.0-service.rc; do
  case "$rel" in
    */bin/*) install_payload 0755 "$rel" ;;
    *) install_payload 0644 "$rel" ;;
  esac
done

# Prevent the obsolete RK3326 audio service from being parsed alongside H616.
if [ -e "$SYSTEM_MOUNT/system/vendor/etc/init/android.hardware.audio.service.rc.rk3326-disabled" ]; then
  backup_existing system/vendor/etc/init/android.hardware.audio.service.rc.rk3326-disabled
  rm -f "$SYSTEM_MOUNT/system/vendor/etc/init/android.hardware.audio.service.rc.rk3326-disabled"
fi
sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
verify_rel() {
  rel=$1
  expected=$(grep -F "  $rel" "$MANIFEST" | tail -n 1)
  test -n "$expected"
  (cd "$VERIFY_MOUNT" && printf '%s\n' "$expected" | sha256sum -c -)
}
for rel in \
  system/vendor/bin/hw/android.hardware.audio@2.0-service \
  system/vendor/lib/hw/android.hardware.audio@5.0-impl.so \
  system/vendor/lib/hw/android.hardware.audio.effect@5.0-impl.so \
  system/vendor/lib/hw/audio.primary.cupid.so \
  system/vendor/lib/hw/audio.primary.rk3326.so \
  system/vendor/lib/hw/audio.primary.default.so \
  system/vendor/lib/libtinyalsa_audio.so \
  system/vendor/lib/libwebrtc_audio_preprocessing.so \
  system/vendor/lib/soundfx/libaudiopreprocessing.so \
  system/vendor/lib/android.hardware.audio.common-util.so \
  system/vendor/lib/android.hardware.audio.common@5.0-util.so \
  system/vendor/etc/vintf/manifest.xml \
  system/vendor/etc/audio_policy_configuration.xml \
  system/vendor/etc/audio/audio_policy_configuration.xml \
  system/vendor/etc/audio_platform_info.xml \
  system/vendor/etc/audio_mixer_paths.xml \
  system/vendor/etc/audio_effects.xml \
  system/vendor/etc/init/android.hardware.audio@2.0-service.rc; do
  verify_rel "$rel"
done
grep -q '<version>5.0</version>' "$VERIFY_MOUNT/system/vendor/etc/vintf/manifest.xml"
test -x "$VERIFY_MOUNT/system/vendor/bin/hw/android.hardware.audio@2.0-service"
test ! -e "$VERIFY_MOUNT/system/vendor/etc/init/android.hardware.audio.service.rc.rk3326-disabled"
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo BUILD_DATE=2026-09-02
  echo FIX=fix58
  echo BASELINE='H616 Android 10 audio; H618 not used'
  echo PATCH_SEMANTICS='Replace accidental @6.0/RK3326 audio with H616 @5.0 service, HAL, policy and mixer configuration'
  echo DATA_FSCK_NOT_NEEDED=1
} | tee "$PREP_LOG"
