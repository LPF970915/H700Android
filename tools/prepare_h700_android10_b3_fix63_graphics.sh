#!/bin/sh
set -eu

BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ENV_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
BASE_SHA=6f65dd6571f80b07beb1329b058bb1f0b113c94f8d4f9f153fbd9f9274c2eb37
OLD_RAMDISK_SHA=a594e65d7434f57f3ce3ce6026109f0d6a5dbdb2349ce7dd4271a062e7e269a1
NEW_RAMDISK_SHA=${RGSP_RAMDISK_SHA:-485d163b4d3700b21a97265245e6eb0b53a44b283ca537655780d186392335db}
NEW_RAMDISK_SIZE=${RGSP_RAMDISK_SIZE:-2604994}
HWC_SOURCE=${RGSP_HWC_SOURCE:-hwcomposer.cupid.fix63.so}
PAYLOAD_MANIFEST=${RGSP_PAYLOAD_MANIFEST:-fix63-payload.sha256}
STAGE=${RGSP_STAGE:-A10-B3-FIX63-GRAPHICS}
SOFTWARE_VSYNC=${RGSP_SOFTWARE_VSYNC:-false}
EGL_XZ_SOURCE=${RGSP_EGL_XZ_SOURCE:-libGLES_mali.arm32.r20p0.so.xz}
EGL_SHA=05dc81f866b7ab947d20f283f25dcd96ca2f56ffd48e637b68778c1a994a6925
MALI_MODULE_XZ_SOURCE=${RGSP_MALI_MODULE_XZ_SOURCE:-mali_kbase.h700.r20p0.ko.xz}
MALI_MODULE_SHA=987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9
MALI_MODULE_SIZE=17590792
B=/mnt/sdcard
S=/mnt/rgsp-fix63-system
V=/mnt/rgsp-fix63-vendor
D=/mnt/rgsp-fix63-data
R="$B/${RGSP_RAMDISK_NAME:-ramdisk-a10-handoff-fix63.gz}"
BOOT=/run/rgsp-fix63-boot.img
BACKUP="$B/fix63-pre"
sha() { sha256sum "$1" | awk '{print $1}'; }

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7
test "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b
test "$(sha /dev/mmcblk0p4)" = "$BOOT_SHA"
test "$(sha "$B/rgsp-linux-boot-original.img")" = "$BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ENV_SHA"
test ! -e "$B/RGSP_ANDROID_TRY.ONCE"
test "$(sha "$B/h700-android10-b3-diag3-boot.img.gz9")" = "$BASE_SHA"
test "$(sha "$B/ramdisk-a10-handoff-fix61-chroot-boot-complete-watchdog.gz9")" = "$OLD_RAMDISK_SHA"
cd "$B"
sha256sum -c "$PAYLOAD_MANIFEST"
python3 "$B/replace_ramdisk_init.py" \
    "$B/ramdisk-a10-handoff-fix61-chroot-boot-complete-watchdog.gz9" \
    "$B/h700_android10_b3_handoff_init_fix62.sh" "$R"
test "$(sha "$R")" = "$NEW_RAMDISK_SHA"
test "$(stat -c %s "$R")" = "$NEW_RAMDISK_SIZE"

for p in /dev/mmcblk1p2 /dev/mmcblk1p3 /dev/mmcblk1p4; do
    if findmnt -rn -S "$p" >/dev/null; then exit 20; fi
    rc=0
    e2fsck -fy "$p" >"/run/fix63-$(basename "$p")-pre.fsck" 2>&1 || rc=$?
    test "$rc" -le 1
done
mkdir -p "$S" "$V" "$D" "$BACKUP"
mount -t ext4 -o rw /dev/mmcblk1p2 "$S"
trap 'mountpoint -q "$D" && umount "$D"; mountpoint -q "$V" && umount "$V"; mountpoint -q "$S" && umount "$S"' EXIT
mount -t ext4 -o rw /dev/mmcblk1p3 "$V"
mount -t ext4 -o rw /dev/mmcblk1p4 "$D"

# Preserve the pre-test logs and modified files once, without rotating away evidence.
for f in "$B"/RGSP_ANDROID_*_LAST.log; do
    test -f "$f" || continue
    test -f "$BACKUP/$(basename "$f")" || cp "$f" "$BACKUP/"
done
for f in "$S"/system/etc/init/rgsp_fix*_display_nodes.rc; do
    test -f "$f" || continue
    test -f "$BACKUP/$(basename "$f")" || cp "$f" "$BACKUP/"
    rm -f "$f"
done
for rc_name in servicemanager.rc hwservicemanager.rc; do
    rc_path="$S/system/etc/init/$rc_name"
    test -f "$rc_path"
    sed -i '/^[[:space:]]*console[[:space:]]*$/d' "$rc_path"
done
SF_RC="$S/system/etc/init/surfaceflinger.rc"
test -f "$SF_RC"
sed -i 's#^service surfaceflinger .*#service surfaceflinger /system/bin/surfaceflinger#' "$SF_RC"
sed -i '/^[[:space:]]*setenv LD_PRELOAD .*librgsp_mali_ioctl_trace\.so[[:space:]]*$/d' "$SF_RC"
sed -i '/^[[:space:]]*seclabel u:r:surfaceflinger:s0[[:space:]]*$/d' "$SF_RC"
sed -i '/^[[:space:]]*console[[:space:]]*$/d' "$SF_RC"
sed -i '/^[[:space:]]*capabilities SYS_NICE[[:space:]]*$/d' "$SF_RC"
sed -i '/^service surfaceflinger /a\    capabilities SYS_NICE' "$SF_RC"
test "$(grep -c '^service surfaceflinger /system/bin/surfaceflinger$' "$SF_RC")" = 1
test "$(grep -c '^[[:space:]]*capabilities SYS_NICE[[:space:]]*$' "$SF_RC")" = 1
BUILD_PROP="$S/system/build.prop"
test -f "$BUILD_PROP"
for prop in \
    'ro.product.platform=tablet' \
    'debug.hwui.renderer=opengl' \
    'debug.hwui.use_buffer_age=false' \
    'debug.hwui.use_partial_updates=false'; do
    key=${prop%%=*}
    sed -i "/^${key}=.*/d" "$BUILD_PROP"
    printf '%s\n' "$prop" >> "$BUILD_PROP"
done
grep -q '^ro.product.platform=tablet$' "$BUILD_PROP"
grep -q '^debug.hwui.renderer=opengl$' "$BUILD_PROP"
grep -q '^debug.hwui.use_buffer_age=false$' "$BUILD_PROP"
grep -q '^debug.hwui.use_partial_updates=false$' "$BUILD_PROP"
LOGCAT_RC="$S/system/etc/init/rgsp_fix47_logcat.rc"
if [ ! -f "$LOGCAT_RC" ]; then
    cat > "$LOGCAT_RC" <<'EOF'
service rgsp_fix47_logcat /system/bin/sh /system/bin/rgsp-fix47-logcat.sh
    class core
    user root
    group root log
    seclabel u:r:init:s0
EOF
fi
test -f "$LOGCAT_RC"
FEATURE="$S/system/etc/permissions/android.software.app_widgets.xml"
mkdir -p "$(dirname "$FEATURE")"
printf '%s\n' '<permissions><feature name="android.software.app_widgets" /></permissions>' > "$FEATURE"
chmod 0644 "$FEATURE"
USER0="$D/user/0"
test -d "$D/user"
if [ -L "$USER0" ]; then
    test "$(readlink "$USER0")" = /data/data
else
    test -d "$USER0"
    test "$(find "$USER0" -mindepth 1 -maxdepth 1 -print | wc -l)" = 0
    rmdir "$USER0"
    ln -s /data/data "$USER0"
fi
test -L "$USER0"
test "$(readlink "$USER0")" = /data/data
test -d "$D/data/com.android.launcher3"
DISP_DIR="$V/etc/dispconfigs"
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
for prop in \
    'persist.display.policy=single' \
    'persist.disp.device_config=/vendor/etc/dispconfigs/h700-rgsp-lcd.json'; do
    key=${prop%%=*}
    sed -i "/^${key}=.*/d" "$BUILD_PROP"
    printf '%s\n' "$prop" >> "$BUILD_PROP"
done
for rel in ueventd.rc build.prop lib/hw/hwcomposer.cupid.so lib/libdisplayconfig.so lib/egl/libGLES_mali.so; do
    mkdir -p "$BACKUP/vendor/$(dirname "$rel")"
    if [ -f "$V/$rel" ]; then
        test -f "$BACKUP/vendor/$rel" || cp "$V/$rel" "$BACKUP/vendor/$rel"
    fi
done
test -f "$BACKUP/displayservice.rc" || cp "$S/system/etc/init/displayservice.rc" "$BACKUP/"
test -f "$BACKUP/init.rc" || cp "$S/init.rc" "$BACKUP/"
sed -i '/^[[:space:]]*start console[[:space:]]*$/d' "$S/init.rc"
test -f "$BACKUP/rgsp-fix47-logcat.sh" || cp "$S/system/bin/rgsp-fix47-logcat.sh" "$BACKUP/"
install -m 0755 "$B/rgsp-logcat-bounded.sh" "$S/system/bin/rgsp-fix47-logcat.sh"

install -m 0644 "$B/rgsp_fix63_graphics.rc" "$S/system/etc/init/rgsp_fix63_graphics.rc"
install -m 0755 "$B/rgsp-graphics-diag.sh" "$S/system/etc/rgsp-graphics-diag.sh"
mkdir -p "$S/system/lib/modules"
xz -dc "$B/$MALI_MODULE_XZ_SOURCE" > /run/mali_kbase.ko
test "$(stat -c %s /run/mali_kbase.ko)" = "$MALI_MODULE_SIZE"
test "$(sha /run/mali_kbase.ko)" = "$MALI_MODULE_SHA"
install -m 0644 /run/mali_kbase.ko "$S/system/lib/modules/mali_kbase.ko"
rm -f /run/mali_kbase.ko
test "$(stat -c %s "$S/system/lib/modules/mali_kbase.ko")" = "$MALI_MODULE_SIZE"
test "$(sha "$S/system/lib/modules/mali_kbase.ko")" = "$MALI_MODULE_SHA"
mkdir -p "$V/lib/egl"
xz -dc "$B/$EGL_XZ_SOURCE" > /run/libGLES_mali.so
test "$(sha /run/libGLES_mali.so)" = "$EGL_SHA"
install -m 0644 /run/libGLES_mali.so "$V/lib/egl/libGLES_mali.so"
rm -f /run/libGLES_mali.so
install -m 0644 "$B/$HWC_SOURCE" "$V/lib/hw/hwcomposer.cupid.so"
install -m 0644 "$B/libdisplayconfig.fix63.so" "$V/lib/libdisplayconfig.so"
test "$(sha "$V/lib/egl/libGLES_mali.so")" = "$EGL_SHA"
test "$(sha "$V/lib/hw/hwcomposer.cupid.so")" = "$(sha "$B/$HWC_SOURCE")"
test "$(sha "$V/lib/libdisplayconfig.so")" = "$(sha "$B/libdisplayconfig.fix63.so")"
sed -i -E 's@^(/dev/(ion|mali0))[[:space:]].*@\1 0666 system graphics@' "$V/ueventd.rc"
grep -q '^/dev/ion 0666 system graphics$' "$V/ueventd.rc"
grep -q '^/dev/mali0 0666 system graphics$' "$V/ueventd.rc"
case "$SOFTWARE_VSYNC" in true|false) ;; *) exit 22 ;; esac
sed -i '/^persist.vendor.hwc.software_vsync=/d' "$V/build.prop"
printf 'persist.vendor.hwc.software_vsync=%s\n' "$SOFTWARE_VSYNC" >> "$V/build.prop"

# The fixed LCD does not need the Homlet HDMI/CVBS displayservice policy.
sed -i '/^[[:space:]]*start displayservice[[:space:]]*$/d' "$S/system/etc/init/displayservice.rc"
sync
umount "$D"
umount "$V"
umount "$S"
trap - EXIT
for p in /dev/mmcblk1p2 /dev/mmcblk1p3 /dev/mmcblk1p4; do
    rc=0
    e2fsck -fy "$p" >"/run/fix63-$(basename "$p")-post.fsck" 2>&1 || rc=$?
    test "$rc" -le 1
done

gzip -dc "$B/h700-android10-b3-diag3-boot.img.gz9" > "$BOOT"
test "$(stat -c %s "$BOOT")" = 67108864
python3 - "$BOOT" "$R" <<'PY'
import pathlib, struct, sys
boot = pathlib.Path(sys.argv[1])
ramdisk = pathlib.Path(sys.argv[2]).read_bytes()
with boot.open("r+b") as f:
    header = f.read(2048)
    assert header[:8] == b"ANDROID!"
    kernel_size = struct.unpack_from("<I", header, 8)[0]
    page_size = struct.unpack_from("<I", header, 36)[0]
    assert page_size == 2048
    offset = page_size + ((kernel_size + page_size - 1) // page_size) * page_size
    assert offset == 8638 * 2048
    assert offset + len(ramdisk) < boot.stat().st_size
    f.seek(offset)
    f.write(ramdisk)
    f.seek(16)
    f.write(struct.pack("<I", len(ramdisk)))
    f.seek(64)
    f.write(b"selinux=1 enforcing=0 androidboot.selinux=permissive".ljust(512, b"\0"))
PY
NEW_BOOT_SHA=$(sha "$BOOT")
dd if="$BOOT" of=/dev/mmcblk0p4 bs=1M conv=fsync
test "$(sha /dev/mmcblk0p4)" = "$NEW_BOOT_SHA"
printf '%s boot=%s\n' "$STAGE" "$NEW_BOOT_SHA" > "$B/RGSP_ANDROID_TRY.ONCE"
{
    echo STAGE="$STAGE"
    echo BOOT_SHA="$NEW_BOOT_SHA"
    echo RAMDISK_SHA="$NEW_RAMDISK_SHA"
    echo HWC_SHA="$(sha "$B/$HWC_SOURCE")"
    echo EGL_SHA="$EGL_SHA"
    echo MALI_MODULE_SHA="$MALI_MODULE_SHA"
    echo SOFTWARE_VSYNC="$SOFTWARE_VSYNC"
    echo GPU_ION_APP_ACCESS=0666
    echo WATCHDOG=boot_complete_and_same_pids_120s_deadline_600s
} | tee "$B/H700_ANDROID10_B3_PREP_fix63.log"
sync
reboot
