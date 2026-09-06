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
B=/mnt/sdcard
S=/mnt/rgsp-fix63-system
V=/mnt/rgsp-fix63-vendor
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

for p in /dev/mmcblk1p2 /dev/mmcblk1p3; do
    if findmnt -rn -S "$p" >/dev/null; then exit 20; fi
    rc=0
    e2fsck -fy "$p" >"/run/fix63-$(basename "$p")-pre.fsck" 2>&1 || rc=$?
    test "$rc" -le 1
done
mkdir -p "$S" "$V" "$BACKUP"
mount -t ext4 -o rw /dev/mmcblk1p2 "$S"
trap 'mountpoint -q "$V" && umount "$V"; mountpoint -q "$S" && umount "$S"' EXIT
mount -t ext4 -o rw /dev/mmcblk1p3 "$V"

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
for rel in ueventd.rc build.prop lib/hw/hwcomposer.cupid.so lib/libdisplayconfig.so; do
    mkdir -p "$BACKUP/vendor/$(dirname "$rel")"
    test -f "$BACKUP/vendor/$rel" || cp "$V/$rel" "$BACKUP/vendor/$rel"
done
test -f "$BACKUP/displayservice.rc" || cp "$S/system/etc/init/displayservice.rc" "$BACKUP/"
test -f "$BACKUP/init.rc" || cp "$S/init.rc" "$BACKUP/"
sed -i '/^[[:space:]]*start console[[:space:]]*$/d' "$S/init.rc"
test -f "$BACKUP/rgsp-fix47-logcat.sh" || cp "$S/system/bin/rgsp-fix47-logcat.sh" "$BACKUP/"
install -m 0755 "$B/rgsp-logcat-bounded.sh" "$S/system/bin/rgsp-fix47-logcat.sh"

install -m 0644 "$B/rgsp_fix63_graphics.rc" "$S/system/etc/init/rgsp_fix63_graphics.rc"
install -m 0755 "$B/rgsp-graphics-diag.sh" "$S/system/etc/rgsp-graphics-diag.sh"
install -m 0644 "$B/$HWC_SOURCE" "$V/lib/hw/hwcomposer.cupid.so"
install -m 0644 "$B/libdisplayconfig.fix63.so" "$V/lib/libdisplayconfig.so"
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
umount "$V"
umount "$S"
trap - EXIT
for p in /dev/mmcblk1p2 /dev/mmcblk1p3; do
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
    echo SOFTWARE_VSYNC="$SOFTWARE_VSYNC"
    echo GPU_ION_APP_ACCESS=0666
    echo WATCHDOG=boot_complete_and_same_pids_120s_deadline_600s
} | tee "$B/H700_ANDROID10_B3_PREP_fix63.log"
sync
reboot
