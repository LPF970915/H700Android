#!/bin/sh
# RGSP H700 single-card Android prototype.
# The bootloader must load this ramdisk from the same card whose partitions
# are exposed as mmcblk0. This file deliberately has no TF1 recovery path.
set -eu

exec </dev/console >/dev/console 2>&1
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mkdir -p /dev/pts /dev/socket /android-root /single-card-roms
mount -t devpts devpts /dev/pts 2>/dev/null || true

SYSTEM_DEV=/dev/mmcblk0p5
VENDOR_DEV=/dev/mmcblk0p6
DATA_DEV=/dev/mmcblk0p7
ROMS_DEV=/dev/mmcblk0p8
LOG=/single-card-roms/RGSP_SINGLE_CARD_BOOT.log

fail() {
    echo "[rgsp-single-card] ERROR: $*"
    echo "[rgsp-single-card] ERROR: $*" >> "$LOG" 2>/dev/null || true
    exec /bin/ash
}

echo '[rgsp-single-card] single-card init reached'
tries=0
while [ "$tries" -lt 30 ]; do
    [ -b "$SYSTEM_DEV" ] && [ -b "$VENDOR_DEV" ] &&
        [ -b "$DATA_DEV" ] && [ -b "$ROMS_DEV" ] && break
    echo "[rgsp-single-card] waiting for mmcblk0 partitions ($tries/30)"
    sleep 1
    tries=$((tries + 1))
done

[ -b "$SYSTEM_DEV" ] || fail "missing $SYSTEM_DEV"
[ -b "$VENDOR_DEV" ] || fail "missing $VENDOR_DEV"
[ -b "$DATA_DEV" ] || fail "missing $DATA_DEV"
[ -b "$ROMS_DEV" ] || fail "missing $ROMS_DEV"

mount -t vfat -o rw "$ROMS_DEV" /single-card-roms ||
    fail "unable to mount $ROMS_DEV"
touch "$LOG"
echo '[rgsp-single-card] ROMS partition mounted' >> "$LOG"

mount -t ext4 -o ro "$SYSTEM_DEV" /android-root ||
    fail "unable to mount Android system"
mkdir -p /android-root/vendor /android-root/data
mount -t ext4 -o ro "$VENDOR_DEV" /android-root/vendor ||
    fail "unable to mount Android vendor"
# The kernel mounts data here; do not run the historical offline repair flow.
mount -t ext4 -o rw,noatime,nosuid,nodev,noauto_da_alloc "$DATA_DEV" \
    /android-root/data || fail "unable to mount Android data"

[ -x /android-root/system/bin/init ] ||
    fail 'Android /system/bin/init is missing'
[ -d /android-root/system/apex ] || fail 'system/apex is missing'
[ -d /android-root/apex ] || fail 'apex mount point is missing'
mount -t tmpfs -o mode=0755,nosuid,nodev,noexec tmpfs /android-root/apex ||
    fail 'unable to mount writable apex'

mount -o bind /dev /android-root/dev || fail 'unable to bind /dev'
for node in binder hwbinder vndbinder; do
    [ -c "/dev/$node" ] || fail "missing inherited $node"
    chown 0:0 "/dev/$node"
    chmod 0666 "/dev/$node"
done
for node in ion mali0 disp fb0 g2d; do
    [ -c "/dev/$node" ] || continue
    chown 1000:1003 "/dev/$node"
    chmod 0660 "/dev/$node"
done
mkdir -p /dev/graphics /dev/block/by-partuuid
if [ -c /dev/fb0 ]; then
    ln -snf /dev/fb0 /dev/graphics/fb0
fi
for node in /dev/snd/*; do
    [ -c "$node" ] || continue
    chown 1000:1005 "$node"
    chmod 0660 "$node"
done
for spec in \
    '096d7fa1-62e8-c242-9876-cfdd5a92b8eb:mmcblk0p5' \
    '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8:mmcblk0p6' \
    '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed:mmcblk0p7'; do
    uuid=${spec%%:*}
    device=${spec#*:}
    ln -snf "/dev/$device" \
        "/android-root/dev/block/by-partuuid/$uuid"
done

mount -o bind /proc /android-root/proc || fail 'unable to bind /proc'
mount -o bind /sys /android-root/sys || fail 'unable to bind /sys'
mkdir -p /android-root/sys/fs/selinux
mountpoint -q /android-root/sys/fs/selinux ||
    mount -t selinuxfs selinuxfs /android-root/sys/fs/selinux ||
    fail 'unable to mount selinuxfs'
[ -e /android-root/sys/fs/selinux/load ] || fail 'missing SELinux policy load node'
mount -t tmpfs -o mode=0755 tmpfs /android-root/mnt ||
    fail 'unable to mount /mnt'
mount -t tmpfs -o mode=0755 tmpfs /android-root/debug_ramdisk ||
    fail 'unable to mount debug ramdisk'

mount -o bind /single-card-roms /android-root/rgsp-persist ||
    fail 'unable to bind persistent ROMS storage'
echo '[rgsp-single-card] Android root ready; switching root' >> "$LOG"

INIT_STARTED_AT=$(awk '{printf "%d", $1 * 1000}' /proc/uptime)
INIT_SELINUX_TOOK=0
export INIT_STARTED_AT INIT_SELINUX_TOOK
: > /dev/.coldboot_done
chmod 0000 /dev/.coldboot_done
sync
exec /bin/busybox switch_root /android-root /init selinux_setup
