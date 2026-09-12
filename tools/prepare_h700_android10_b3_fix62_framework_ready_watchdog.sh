#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
BASE_BOOT_GZ=/mnt/sdcard/h700-android10-b3-diag3-boot.img.gz9
BASE_BOOT_GZ_SHA=6f65dd6571f80b07beb1329b058bb1f0b113c94f8d4f9f153fbd9f9274c2eb37
RAMDISK=/mnt/sdcard/ramdisk-a10-handoff-fix62-framework-ready-watchdog.gz9
RAMDISK_SHA=REPLACE_RAMDISK_SHA
RAMDISK_SIZE=REPLACE_RAMDISK_SIZE
RAMDISK_SIZE_ESCAPED='REPLACE_RAMDISK_SIZE_ESCAPED'
MODULE_SHA=987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9
DEVICES_RC_SOURCE=/mnt/sdcard/rgsp_fix60_display_nodes.rc
DEVICES_RC_SHA=852a33f5ca7cd0aaf5949433d86f6cd27721520ae8745096287342a495c7562e
SYSTEM_MOUNT=/mnt/rgsp-a10-fix62-system
VENDOR_MOUNT=/mnt/rgsp-a10-fix62-vendor
DATA_MOUNT=/mnt/rgsp-a10-fix62-data
BOOT_IMAGE=/run/h700-android10-b3-fix62-boot.img
MARKER=/mnt/sdcard/RGSP_ANDROID_TRY.ONCE
PREP_LOG=/mnt/sdcard/H700_ANDROID10_B3_PREP_fix62.log
FEATURE_REL=system/etc/permissions/android.software.app_widgets.xml
FEATURE_CONTENT='<permissions><feature name="android.software.app_widgets" /></permissions>'

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
test "$(sha256sum /mnt/sdcard/rgsp-linux-boot-original.img | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(sha256sum "$BASE_BOOT_GZ" | awk '{print $1}')" = "$BASE_BOOT_GZ_SHA"
test "$(stat -c %s "$RAMDISK")" = "$RAMDISK_SIZE"
test "$(sha256sum "$RAMDISK" | awk '{print $1}')" = "$RAMDISK_SHA"
test "$(sha256sum "$DEVICES_RC_SOURCE" | awk '{print $1}')" = "$DEVICES_RC_SHA"
test ! -e "$MARKER"

findmnt -rn -S /dev/mmcblk1p2 >/dev/null 2>&1 && exit 20
findmnt -rn -S /dev/mmcblk1p3 >/dev/null 2>&1 && exit 20
findmnt -rn -S /dev/mmcblk1p4 >/dev/null 2>&1 && exit 20

fsck_rc=0
e2fsck -fy /dev/mmcblk1p2 >/run/fix54-system-pre.fsck.log 2>&1 || fsck_rc=$?
test "$fsck_rc" -le 1
fsck_rc=0
e2fsck -fy /dev/mmcblk1p3 >/run/fix60-vendor-pre.fsck.log 2>&1 || fsck_rc=$?
test "$fsck_rc" -le 1
fsck_rc=0
e2fsck -fy /dev/mmcblk1p4 >/run/fix54-data-pre.fsck.log 2>&1 || fsck_rc=$?
test "$fsck_rc" -le 1

mkdir -p "$SYSTEM_MOUNT" "$VENDOR_MOUNT" "$DATA_MOUNT"
mount -t ext4 -o rw /dev/mmcblk1p2 "$SYSTEM_MOUNT"
mount -t ext4 -o rw /dev/mmcblk1p3 "$VENDOR_MOUNT"
mount -t ext4 -o rw /dev/mmcblk1p4 "$DATA_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true; mountpoint -q "$VENDOR_MOUNT" && umount "$VENDOR_MOUNT" || true; mountpoint -q "$DATA_MOUNT" && umount "$DATA_MOUNT" || true' EXIT

SF_RC="$SYSTEM_MOUNT/system/etc/init/surfaceflinger.rc"
SF_BIN="$SYSTEM_MOUNT/system/bin/surfaceflinger"
BUILD_PROP="$SYSTEM_MOUNT/system/build.prop"
DISPLAY_SERVICE_RC="$SYSTEM_MOUNT/system/etc/init/displayservice.rc"
test -f "$SF_RC"
test -x "$SF_BIN"
test -f "$BUILD_PROP"
test -f "$DISPLAY_SERVICE_RC"
test "$(sha256sum "$SYSTEM_MOUNT/system/lib/modules/mali_kbase.ko" | awk '{print $1}')" = "$MODULE_SHA"

sed -i 's#^service surfaceflinger .*#service surfaceflinger /system/bin/surfaceflinger#' "$SF_RC"
sed -i '/^[[:space:]]*setenv LD_PRELOAD .*librgsp_mali_ioctl_trace\.so[[:space:]]*$/d' "$SF_RC"
sed -i '/^[[:space:]]*capabilities SYS_NICE[[:space:]]*$/d' "$SF_RC"
sed -i '/^[[:space:]]*seclabel u:r:surfaceflinger:s0[[:space:]]*$/d' "$SF_RC"
sed -i '/^[[:space:]]*console[[:space:]]*$/d' "$SF_RC"
sed -i '/^service surfaceflinger /a\    capabilities SYS_NICE' "$SF_RC"
test "$(grep -c '^service surfaceflinger /system/bin/surfaceflinger$' "$SF_RC")" = 1
test "$(grep -c '^[[:space:]]*capabilities SYS_NICE[[:space:]]*$' "$SF_RC")" = 1

test "$(grep -c '^ro.product.platform=' "$BUILD_PROP")" = 1
platform=$(sed -n 's/^ro.product.platform=//p' "$BUILD_PROP")
case "$platform" in
  homlet)
    cp "$BUILD_PROP" /mnt/sdcard/build.prop.pre-fix54
    sed -i 's/^ro.product.platform=homlet$/ro.product.platform=tablet/' "$BUILD_PROP"
    ;;
  tablet)
    ;;
  *)
    echo "unexpected ro.product.platform: $platform" >&2
    exit 21
    ;;
esac
test "$(grep -c '^ro.product.platform=tablet$' "$BUILD_PROP")" = 1

# Avoid the H700 EGL partial-damage abort by forcing full-frame OpenGL work.
for prop in \
  'debug.hwui.renderer=opengl' \
  'debug.hwui.use_buffer_age=false' \
  'debug.hwui.use_partial_updates=false'; do
  key=${prop%%=*}
  sed -i "/^${key}=.*/d" "$BUILD_PROP"
  printf '%s\n' "$prop" >> "$BUILD_PROP"
done
grep -q '^debug.hwui.renderer=opengl$' "$BUILD_PROP"
grep -q '^debug.hwui.use_buffer_age=false$' "$BUILD_PROP"
grep -q '^debug.hwui.use_partial_updates=false$' "$BUILD_PROP"

rm -f \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix50_mali.rc" \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix51_devices.rc" \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix53_devices.rc" \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix54_devices.rc" \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix57_display_nodes.rc" \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix58_display_nodes.rc" \
  "$SYSTEM_MOUNT/system/etc/init/rgsp_fix60_display_nodes.rc"
install -o 0 -g 0 -m 0644 "$DEVICES_RC_SOURCE" "$SYSTEM_MOUNT/system/etc/init/rgsp_fix60_display_nodes.rc"
test "$(sha256sum "$SYSTEM_MOUNT/system/etc/init/rgsp_fix60_display_nodes.rc" | awk '{print $1}')" = "$DEVICES_RC_SHA"

# H616/H618 publish the permanent LCD through the display configuration
# service. Start it before SurfaceFlinger and force a single-display policy.
cp "$DISPLAY_SERVICE_RC" /mnt/sdcard/displayservice.rc.pre-fix60
sed -i '/^[[:space:]]*start displayservice[[:space:]]*$/d' "$DISPLAY_SERVICE_RC"
printf '%s\n' 'on boot' '    start displayservice' >> "$DISPLAY_SERVICE_RC"
test "$(grep -c '^[[:space:]]*start displayservice[[:space:]]*$' "$DISPLAY_SERVICE_RC")" = 1

for prop in \
  'persist.display.policy=single' \
  'persist.disp.device_config=/vendor/etc/dispconfigs/h700-rgsp-lcd.json'; do
  key=${prop%%=*}
  sed -i "/^${key}=.*/d" "$BUILD_PROP"
  printf '%s\n' "$prop" >> "$BUILD_PROP"
done
grep -q '^persist.display.policy=single$' "$BUILD_PROP"
grep -q '^persist.disp.device_config=/vendor/etc/dispconfigs/h700-rgsp-lcd.json$' "$BUILD_PROP"

DISP_DIR="$VENDOR_MOUNT/etc/dispconfigs"
mkdir -p "$DISP_DIR"
cat > "$DISP_DIR/config.json" <<'EOF'
{
  "DeviceConfig": "h700-rgsp-lcd.json"
}
EOF
cat > "$DISP_DIR/h700-rgsp-lcd.json" <<'EOF'
{
  "DisplayEngineVersion": 2,
  "DisplayNumber": 2,
  "Display0": {
    "InterfaceType": "LCD",
    "DisplayEnginePortId": 0,
    "OverrideFramebufferSize": 1,
    "FramebufferWidth": 720,
    "FramebufferHeight": 480,
    "DpiX": 160,
    "DpiY": 160,
    "HotplugSupported": 0,
    "AfbcSupported": 0,
    "HardwareRotateSupported": 0,
    "BandwidthLimited": 338800,
    "DefaultOutputMode": 0
  },
  "Display1": {
    "InterfaceType": "HDMI",
    "DisplayEnginePortId": 1,
    "OverrideFramebufferSize": 1,
    "FramebufferWidth": 720,
    "FramebufferHeight": 480,
    "DpiX": 160,
    "DpiY": 160,
    "HotplugSupported": 1,
    "AfbcSupported": 0,
    "HardwareRotateSupported": 0,
    "BandwidthLimited": 338800,
    "DefaultOutputMode": 0
  }
}
EOF
chmod 0644 "$DISP_DIR/config.json" "$DISP_DIR/h700-rgsp-lcd.json"
test "$(grep -c 'InterfaceType.*LCD' "$DISP_DIR/h700-rgsp-lcd.json")" = 1

USER0="$DATA_MOUNT/user/0"
test -d "$DATA_MOUNT/user"
if [ -L "$USER0" ]; then
  test "$(readlink "$USER0")" = /data/data
else
  test -d "$USER0"
  test "$(find "$USER0" -mindepth 1 -maxdepth 1 -print | wc -l)" = 0
  rmdir "$USER0"
  ln -s /data/data "$USER0"
  test -L "$USER0"
  test "$(readlink "$USER0")" = /data/data
fi
test -d "$DATA_MOUNT/data/com.android.launcher3"
test "$(stat -c '%u:%g' "$DATA_MOUNT/data/com.android.launcher3")" = 10139:10139

FEATURE="$SYSTEM_MOUNT/$FEATURE_REL"
mkdir -p "$(dirname "$FEATURE")"
printf '%s\n' "$FEATURE_CONTENT" > "$FEATURE"
chmod 0644 "$FEATURE"
test "$(cat "$FEATURE")" = "$FEATURE_CONTENT"

sync
umount "$DATA_MOUNT"
umount "$VENDOR_MOUNT"
umount "$SYSTEM_MOUNT"
trap - EXIT

fsck_rc=0
e2fsck -fy /dev/mmcblk1p4 >/run/fix54-data-post.fsck.log 2>&1 || fsck_rc=$?
test "$fsck_rc" -le 1
fsck_rc=0
e2fsck -fy /dev/mmcblk1p2 >/run/fix54-system-post.fsck.log 2>&1 || fsck_rc=$?
test "$fsck_rc" -le 1
fsck_rc=0
e2fsck -fy /dev/mmcblk1p3 >/run/fix60-vendor-post.fsck.log 2>&1 || fsck_rc=$?
test "$fsck_rc" -le 1

rm -f "$BOOT_IMAGE"
gzip -dc "$BASE_BOOT_GZ" > "$BOOT_IMAGE"
test "$(stat -c %s "$BOOT_IMAGE")" = 67108864
dd if="$RAMDISK" of="$BOOT_IMAGE" bs=2048 seek=8638 conv=notrunc status=none
printf "$RAMDISK_SIZE_ESCAPED" | dd of="$BOOT_IMAGE" bs=1 seek=16 conv=notrunc status=none
dd if=/dev/zero of="$BOOT_IMAGE" bs=1 seek=64 count=512 conv=notrunc status=none
printf '%s' 'selinux=1 enforcing=0 androidboot.selinux=permissive' | dd of="$BOOT_IMAGE" bs=1 seek=64 conv=notrunc status=none
BOOT_SHA=$(sha256sum "$BOOT_IMAGE" | awk '{print $1}')

rm -f \
  /mnt/sdcard/RGSP_ANDROID_BOOT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_INIT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_KMSG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_PROC_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_LOGCAT_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_FIX47_EGL_DIAG_LAST.log \
  /mnt/sdcard/RGSP_ANDROID_SURFACEFLINGER_STRACE_LAST.log

dd if="$BOOT_IMAGE" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$BOOT_SHA"
printf '%s boot=%s\n' 'h700 android10 b3 fix62 framework-ready-watchdog' "$BOOT_SHA" > "$MARKER"
sync

{
  echo DATE="$(date -u 2>/dev/null || date 2>/dev/null || true)"
  echo STAGE=A10-B3-FIX62-FRAMEWORK-READY-WATCHDOG
  echo BOOT_WRITTEN_SHA="$BOOT_SHA"
  echo INIT_RC=/system/etc/init/rgsp_fix60_display_nodes.rc
  echo PRODUCT_PLATFORM=tablet
  echo DATA_USER0_SYMLINK=/data/data
  echo APPWIDGET_FEATURE=/system/etc/permissions/android.software.app_widgets.xml
  echo HWUI_RENDERER=opengl
  echo DISPLAY_FB_ALIAS=/dev/graphics/fb0
  echo DISPLAY_NODE_OWNER=system:graphics
  echo DISPLAY_SERVICE_EARLY_START=1
  echo DISPLAY_POLICY=single
  echo DISPLAY_CONFIG=/vendor/etc/dispconfigs/h700-rgsp-lcd.json
  echo HANDOFF_RAMDISK_SHA="$RAMDISK_SHA"
  echo WAKE_LOCK=rgsp_android_bringup
} | tee "$PREP_LOG"

reboot
