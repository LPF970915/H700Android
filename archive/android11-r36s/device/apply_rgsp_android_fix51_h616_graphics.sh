#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
FIX50_SYSTEM_PROP_SHA=618a7a6413212b6a6f0ec7074564c258f76d8507080b72129e09a7a4a081aa66
FIX50_VENDOR_PROP_SHA=3a28473a194996ca0051f153fc2f046b7ff81db98d394914f21818dccf5e8eb1
FIX50_MANIFEST_SHA=2fabfd3acb79522a46c22cd553acf96de028823960b7f334bfb47c7bfd1bc288
FIX50_SF_RC_SHA=656b9bf4c47f356a0be9ec0a7aa70ee4b16aa6887a86fc75a62852cc26bc57b3
FIX50_BOOTANIM_RC_SHA=d7854acbd566ba7985fefa5aa87602c42814ed5a7ea5904d2628ac4f9444f77f
FIX50_ALLOC_RC_SHA=a139a3fd898f2c8404efbb51646814a2ec5cb848f8135bbc63d1b829c142037d
FIX50_COMPOSER21_RC_SHA=2272ae38541f35caa05f7ca426f690e32b92c930622317e925e7796a29708bfa
FIX50_ALLOC_SERVICE_SHA=55898423fb67f3830a7f2e3abe099eeb74a526b7326ca088e6f62a35d962a2da
FIX50_ALLOC_IMPL_SHA=2eab2f6b95def546e4ccefacfb3e8789db99de06fbaf32df83060d8d17c12939
FIX50_MALI32_SHA=3d33f67af54b44ff191eafe703835af3c6aa747b3fceff87a312f889e5d9ff9d
FIX50_MALI64_SHA=0dd74b4291fdf45eb4a29bca13d524b5d54f9e7b7aec4ef48ff4008daf9aae1f
MAPPER32_SHA=7b7d1588c99b634d63690fb9b9219d936e11d538761e86b1ce37bfe875c3acdb
MAPPER64_SHA=dde77a1b7768dfc8ca2d69d710ef2f3c2f7daf594ab57f9dcfa001683111fd2b
FIX49_SERVICES_SHA=5b4ded60538f0a0a4903b56933eaa9527b11585028d9d9fc1e483fe52f8d3ce1
FIX50_LIBSELINUX_SHA=699d914d8228dc370993f56cdea07d04b6bc20c35033c0b3be5672954a659ef4

PAYLOAD=/tmp/rgsp-fix51-payload
MANIFEST=/tmp/rgsp-fix51-payload.sha256
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix51
VERIFY_MOUNT=/mnt/rgsp-system-fix51-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX51_BACKUP
PREP_LOG=/tmp/RGSP_ANDROID_FIX51_SYSTEM_PREP.log

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
VINTF_MANIFEST=$SYSTEM_MOUNT/system/vendor/etc/vintf/manifest.xml
SF_DISABLED=$SYSTEM_MOUNT/system/etc/init/surfaceflinger.rc.rk3326-disabled
BOOTANIM_DISABLED=$SYSTEM_MOUNT/system/etc/init/bootanim.rc.rk3326-disabled
ALLOC_RC_DISABLED=$SYSTEM_MOUNT/system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled
COMPOSER21_RC_DISABLED=$SYSTEM_MOUNT/system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled
DISABLED_INIT_DIR=$SYSTEM_MOUNT/system/rgsp-disabled-init/fix51
ALLOC_SERVICE=$SYSTEM_MOUNT/system/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service
ALLOC_IMPL=$SYSTEM_MOUNT/system/vendor/lib/hw/android.hardware.graphics.allocator@2.0-impl.so
MALI32=$SYSTEM_MOUNT/system/vendor/lib/egl/libGLES_mali.so
MALI64=$SYSTEM_MOUNT/system/vendor/lib64/egl/libGLES_mali.so

test "$(sha256sum "$SYSTEM_PROP" | awk '{print $1}')" = "$FIX50_SYSTEM_PROP_SHA"
test "$(sha256sum "$VENDOR_PROP" | awk '{print $1}')" = "$FIX50_VENDOR_PROP_SHA"
test "$(sha256sum "$VINTF_MANIFEST" | awk '{print $1}')" = "$FIX50_MANIFEST_SHA"
test "$(sha256sum "$SF_DISABLED" | awk '{print $1}')" = "$FIX50_SF_RC_SHA"
test "$(sha256sum "$BOOTANIM_DISABLED" | awk '{print $1}')" = "$FIX50_BOOTANIM_RC_SHA"
test "$(sha256sum "$ALLOC_RC_DISABLED" | awk '{print $1}')" = "$FIX50_ALLOC_RC_SHA"
test "$(sha256sum "$COMPOSER21_RC_DISABLED" | awk '{print $1}')" = "$FIX50_COMPOSER21_RC_SHA"
test "$(sha256sum "$ALLOC_SERVICE" | awk '{print $1}')" = "$FIX50_ALLOC_SERVICE_SHA"
test "$(sha256sum "$ALLOC_IMPL" | awk '{print $1}')" = "$FIX50_ALLOC_IMPL_SHA"
test "$(sha256sum "$MALI32" | awk '{print $1}')" = "$FIX50_MALI32_SHA"
test "$(sha256sum "$MALI64" | awk '{print $1}')" = "$FIX50_MALI64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so" | awk '{print $1}')" = "$MAPPER32_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so" | awk '{print $1}')" = "$MAPPER64_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX50_LIBSELINUX_SHA"
test "$(grep -Fxc 'ro.config.headless=1' "$SYSTEM_PROP")" = 1
for property in ro.hardware.gralloc ro.hardware.hwcomposer ro.hardware.egl; do
  ! grep -q "^$property=" "$VENDOR_PROP"
done

for relative in \
  system/etc/init/surfaceflinger.rc \
  system/etc/init/bootanim.rc \
  system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc \
  system/vendor/etc/init/android.hardware.graphics.composer@2.2-service.rc \
  system/vendor/bin/hw/android.hardware.graphics.composer@2.2-service \
  system/vendor/lib/hw/gralloc.cupid.so \
  system/vendor/lib64/hw/gralloc.cupid.so \
  system/vendor/lib/hw/hwcomposer.cupid.so \
  system/vendor/etc/vintf/manifest/vendor.display.config@1.0.xml \
  system/vendor/lib/libdisplayconfig.so \
  system/vendor/lib/libdisplayd.so \
  system/vendor/lib/libedid.so \
  system/vendor/lib/libhidltransport.so \
  system/vendor/lib/libhwbinder.so \
  system/vendor/lib/libhwc2on1adapter.so \
  system/vendor/lib/libhwc2onfbadapter.so \
  system/vendor/lib/libsync_aw.so \
  system/vendor/lib/vendor.display.config@1.0-impl.so \
  system/vendor/lib/vendor.display.config@1.0.so; do
  test ! -e "$SYSTEM_MOUNT/$relative"
done

backup_file() {
  relative=$1
  mkdir -p "$BACKUP_DIR/$(dirname "$relative")"
  cp "$SYSTEM_MOUNT/$relative" "$BACKUP_DIR/$relative"
  test "$(sha256sum "$SYSTEM_MOUNT/$relative" | awk '{print $1}')" = \
    "$(sha256sum "$BACKUP_DIR/$relative" | awk '{print $1}')"
}

backup_file system/build.prop
backup_file system/vendor/build.prop
backup_file system/vendor/etc/vintf/manifest.xml
backup_file system/etc/init/surfaceflinger.rc.rk3326-disabled
backup_file system/etc/init/bootanim.rc.rk3326-disabled
backup_file system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled
backup_file system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled
backup_file system/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service
backup_file system/vendor/lib/hw/android.hardware.graphics.allocator@2.0-impl.so
backup_file system/vendor/lib/egl/libGLES_mali.so
backup_file system/vendor/lib64/egl/libGLES_mali.so

install_payload() {
  mode=$1
  relative=$2
  install -D -o 0 -g 0 -m "$mode" "$PAYLOAD/$relative" "$SYSTEM_MOUNT/$relative"
}

install_payload 0644 system/etc/init/surfaceflinger.rc
install_payload 0644 system/etc/init/bootanim.rc
install_payload 0755 system/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service
install_payload 0755 system/vendor/bin/hw/android.hardware.graphics.composer@2.2-service
install_payload 0644 system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc
install_payload 0644 system/vendor/etc/init/android.hardware.graphics.composer@2.2-service.rc
install_payload 0644 system/vendor/etc/vintf/manifest.xml
install_payload 0644 system/vendor/etc/vintf/manifest/vendor.display.config@1.0.xml

for relative in \
  system/etc/init/surfaceflinger.rc.rk3326-disabled \
  system/etc/init/bootanim.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled; do
  destination=$DISABLED_INIT_DIR/$relative
  mkdir -p "$(dirname "$destination")"
  mv "$SYSTEM_MOUNT/$relative" "$destination"
done

for relative in \
  system/vendor/lib/egl/libGLES_mali.so \
  system/vendor/lib/hw/android.hardware.graphics.allocator@2.0-impl.so \
  system/vendor/lib/hw/gralloc.cupid.so \
  system/vendor/lib/hw/hwcomposer.cupid.so \
  system/vendor/lib/libdisplayconfig.so \
  system/vendor/lib/libdisplayd.so \
  system/vendor/lib/libedid.so \
  system/vendor/lib/libhidltransport.so \
  system/vendor/lib/libhwbinder.so \
  system/vendor/lib/libhwc2on1adapter.so \
  system/vendor/lib/libhwc2onfbadapter.so \
  system/vendor/lib/libsync_aw.so \
  system/vendor/lib/vendor.display.config@1.0-impl.so \
  system/vendor/lib/vendor.display.config@1.0.so \
  system/vendor/lib64/egl/libGLES_mali.so \
  system/vendor/lib64/hw/gralloc.cupid.so; do
  install_payload 0644 "$relative"
done

sed -i '/^ro.config.headless=1$/d' "$SYSTEM_PROP"
cat >> "$VENDOR_PROP" <<'EOF'

# RGSP fix51: H616 Android 10 graphics baseline
ro.hardware.gralloc=cupid
ro.hardware.hwcomposer=cupid
ro.hardware.egl=mali
EOF

test "$(grep -c '^ro.config.headless=' "$SYSTEM_PROP")" = 0
test "$(grep -Fxc 'ro.hardware.gralloc=cupid' "$VENDOR_PROP")" = 1
test "$(grep -Fxc 'ro.hardware.hwcomposer=cupid' "$VENDOR_PROP")" = 1
test "$(grep -Fxc 'ro.hardware.egl=mali' "$VENDOR_PROP")" = 1
(cd "$SYSTEM_MOUNT" && sha256sum -c "$MANIFEST")
sync

SYSTEM_PROP_SHA=$(sha256sum "$SYSTEM_PROP" | awk '{print $1}')
VENDOR_PROP_SHA=$(sha256sum "$VENDOR_PROP" | awk '{print $1}')
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
(cd "$VERIFY_MOUNT" && sha256sum -c "$MANIFEST")
test "$(sha256sum "$VERIFY_MOUNT/system/build.prop" | awk '{print $1}')" = "$SYSTEM_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/build.prop" | awk '{print $1}')" = "$VENDOR_PROP_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/lib/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so" | awk '{print $1}')" = "$MAPPER32_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/vendor/lib64/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so" | awk '{print $1}')" = "$MAPPER64_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/framework/services.jar" | awk '{print $1}')" = "$FIX49_SERVICES_SHA"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libselinux.so" | awk '{print $1}')" = "$FIX50_LIBSELINUX_SHA"
for relative in \
  system/etc/init/surfaceflinger.rc.rk3326-disabled \
  system/etc/init/bootanim.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc.rk3326-disabled \
  system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc.rk3326-disabled; do
  test ! -e "$VERIFY_MOUNT/$relative"
  test -f "$VERIFY_MOUNT/system/rgsp-disabled-init/fix51/$relative"
done
test "$(grep -c '^ro.config.headless=' "$VERIFY_MOUNT/system/build.prop")" = 0
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-09-01
  echo FIX=fix51
  echo BASELINE='H616 Android 10; H618 not used'
  echo SYSTEM_PROP_SHA="$SYSTEM_PROP_SHA"
  echo VENDOR_PROP_SHA="$VENDOR_PROP_SHA"
  echo GRALLOC64_SHA=3c040df46e4848b3a7ce74fbff585701e45f9349d87962d15fb0a189cd60f1b6
  echo MALI64_SHA=03333d495e3566c7d85ca2e000da569a16ce8f022ea25c0ea61950c891d5c7f8
  echo MAPPER32_SHA="$MAPPER32_SHA"
  echo MAPPER64_SHA="$MAPPER64_SHA"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee "$PREP_LOG"
