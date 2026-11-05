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
if [ -c /dev/ttyS0 ]; then
    exec </dev/ttyS0 >/dev/ttyS0 2>&1
fi
echo '[rgsp-single-card] ROC OS unified userdata ramdisk'

mkdir -p /dev/pts /dev/socket /android-root
mount -t devpts devpts /dev/pts 2>/dev/null || true

LOG=/dev/console

fail() {
    echo "[rgsp-single-card] ERROR: $*"
    echo "[rgsp-single-card] ERROR: $*" >> "$LOG" 2>/dev/null || true
    echo "[roc-user] Offline recovery required; no unauthenticated console."
    while :; do sleep 60; done
}

echo '[rgsp-single-card] single-card init reached'
tries=0
TF1=
while [ "$tries" -lt 30 ]; do
    TF1=
    for sys in /sys/class/block/mmcblk[0-9] /sys/class/block/mmcblk[0-9][0-9]; do
        [ -e "$sys" ] || continue
        case "$(readlink -f "$sys")" in
            */sdc0/mmc_host/*/block/mmcblk*)
                [ -z "$TF1" ] || fail "ambiguous TF1 controller"
                TF1=/dev/${sys##*/}
                ;;
        esac
    done
    if [ -n "$TF1" ] && [ -b "${TF1}p5" ] && [ -b "${TF1}p6" ] && [ -b "${TF1}p7" ]; then break; fi
    tries=$((tries+1)); sleep 1
done
[ -n "$TF1" ] && [ -b "${TF1}p5" ] && [ -b "${TF1}p6" ] && [ -b "${TF1}p7" ] || fail "TF1 is unavailable"
SYSTEM_DEV=${TF1}p5
VENDOR_DEV=${TF1}p6
DATA_DEV=${TF1}p7
/bin/sh /grow/grow-userdata.sh "$TF1" || fail "userdata capacity preparation failed"

mount -t ext4 -o ro "$SYSTEM_DEV" /android-root ||
    fail "unable to mount Android system"
mkdir -p /android-root/vendor /android-root/data
mount -t ext4 -o ro "$VENDOR_DEV" /android-root/vendor ||
    fail "unable to mount Android vendor"
# The kernel mounts data here; do not run the historical offline repair flow.
mount -t ext4 -o rw,noatime,nosuid,nodev,noauto_da_alloc "$DATA_DEV" \
    /android-root/data || fail "unable to mount Android data"
mkdir -p /android-root/data/rgsp-persist
chmod 0700 /android-root/data/rgsp-persist
LOG=/android-root/data/rgsp-persist/RGSP_SINGLE_CARD_BOOT.log
touch "$LOG"
echo '[rgsp-single-card] TF1 internal userdata; TF2 removable' >> "$LOG"

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
# The inherited devtmpfs coldboot has completed before Android starts.
# Hardware ownership and the exact RG34XXSP add-on are prepared before policy
# loading, rather than starting arbitrary shell/su services from Android init.
for node in /dev/input/event*; do
    [ -c "$node" ] || continue
    chown 0:1004 "$node"
    chmod 0660 "$node"
done
[ "$(uname -r)" = 4.9.170 ] || fail "Unexpected kernel ABI for RG34XXSP axes"
[ "$(/bin/busybox sha256sum /android-root/vendor/modules/h700_stick_axes.ko | /bin/busybox cut -d ' ' -f 1)" = 9c8eacf887cd9d00f5416c05b24118ce625e4deef73003f79ea1805c6a31faf5 ] || fail "Stick module identity mismatch"
if ! grep -q '^h700_stick_axes ' /proc/modules; then
    /bin/busybox insmod /android-root/vendor/modules/h700_stick_axes.ko profile=rg34xxsp || fail "Stick module load failed"
fi

mkdir -p /dev/graphics /dev/block/by-partuuid
if [ -c /dev/fb0 ]; then
    ln -snf /dev/fb0 /dev/graphics/fb0
fi
for node in /dev/snd/*; do
    [ -c "$node" ] || continue
    chown 1000:1005 "$node"
    chmod 0660 "$node"
done
mkdir -p /dev/block/by-name
for spec in "system:$SYSTEM_DEV" "vendor:$VENDOR_DEV" "userdata:$DATA_DEV"; do
    name=${spec%%:*}
    device=${spec#*:}
    ln -snf "$device" "/dev/block/by-name/$name"
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

echo '[rgsp-single-card] Android root ready; switching root' >> "$LOG"

INIT_STARTED_AT=$(awk '{printf "%d", $1 * 1000}' /proc/uptime)
INIT_SELINUX_TOOK=0
export INIT_STARTED_AT INIT_SELINUX_TOOK
: > /dev/.coldboot_done
chmod 0000 /dev/.coldboot_done
sync
exec /bin/busybox switch_root /android-root /init selinux_setup
