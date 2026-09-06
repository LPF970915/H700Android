#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin
B=/rgsp-persist
BACKUP="$B/input-precalibration-backup"

[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7 ]
[ "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b ]
[ "$(sha256sum /dev/block/mmcblk0p4 | cut -d ' ' -f 1)" = d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5 ]
[ "$(dd if=/dev/block/mmcblk0p3 bs=131072 count=1 2>/dev/null | sha256sum | cut -d ' ' -f 1)" = d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396 ]
[ "$(sha256sum /vendor/lib/hw/hwcomposer.cupid.so | cut -d ' ' -f 1)" = 89a1f16c3b2b03b3f3250c77f1cae3d35a9995a44281a7538307d8fbbb7fecf2 ]
grep -q '^/dev/mmcblk1p3 /vendor ext4 ro,' /proc/mounts
cd "$B"
sha256sum -c input-precalibration.sha256
mkdir -p "$BACKUP"
if [ ! -f "$BACKUP/baseline.txt" ]; then
    {
        date
        cat /proc/uptime
        pidof surfaceflinger system_server com.android.systemui com.android.launcher3
        ls -lZ /dev/input
        sha256sum /vendor/lib/hw/hwcomposer.cupid.so
    } > "$BACKUP/baseline.txt"
fi

install_file() {
    source="$B/$1"
    target="$2"
    mode="$3"
    if [ -f "$target" ] && cmp -s "$source" "$target"; then
        return
    fi
    if [ -f "$target" ] && [ ! -f "$BACKUP/$1" ]; then
        cp "$target" "$BACKUP/$1"
    fi
    cp "$source" "$target.input-new"
    chmod "$mode" "$target.input-new"
    chown root:root "$target.input-new"
    [ "$(sha256sum "$source" | cut -d ' ' -f 1)" = "$(sha256sum "$target.input-new" | cut -d ' ' -f 1)" ]
    mv "$target.input-new" "$target"
    restorecon "$target"
}

# Unlinking a mapped executable can prevent ext4 remount-ro until it exits.
# Only stop our collector when its installed files actually need replacement.
if ! cmp -s "$B/rgsp_kmsg_logger" /vendor/bin/rgsp_kmsg_logger ||
   ! cmp -s "$B/rgsp-kmsg-start.sh" /vendor/bin/rgsp-kmsg-start.sh; then
    if [ -n "$(getprop init.svc.rgsp-kmsg-bounded)" ]; then
        setprop ctl.stop rgsp-kmsg-bounded
        sleep 1
    fi
    for process in /proc/[0-9]*; do
        command=$(tr '\000' ' ' 2>/dev/null < "$process/cmdline") || continue
        case "$command" in
            "rgsp_kmsg_logger /rgsp-persist/RGSP_ANDROID_KMSG_BOUNDED.log "|"/vendor/bin/rgsp_kmsg_logger /rgsp-persist/RGSP_ANDROID_KMSG_BOUNDED.log ")
                kill -TERM "${process##*/}" 2>/dev/null || true ;;
            "sh /vendor/bin/rgsp-kmsg-start.sh "|"/system/bin/sh /vendor/bin/rgsp-kmsg-start.sh ")
                kill -TERM "${process##*/}" 2>/dev/null || true ;;
        esac
    done
    sleep 1
    if pidof rgsp_kmsg_logger >/dev/null; then
        echo "collector still running; no vendor files changed" >&2
        exit 1
    fi
fi

mount -o remount,rw /vendor
trap 'sync; mount -o remount,ro /vendor' EXIT
install_file rgsp_kmsg_logger /vendor/bin/rgsp_kmsg_logger 0755
install_file rgsp-input-prepare.sh /vendor/bin/rgsp-input-prepare.sh 0755
install_file rgsp-kmsg-start.sh /vendor/bin/rgsp-kmsg-start.sh 0755
install_file rgsp-input-bringup.rc /vendor/etc/init/rgsp-input-bringup.rc 0644
sync
mount -o remount,ro /vendor
trap - EXIT

if ! pidof rgsp_kmsg_logger >/dev/null; then
    if [ -n "$(getprop init.svc.rgsp-kmsg-bounded)" ]; then
        setprop ctl.start rgsp-kmsg-bounded
    else
        nohup sh /vendor/bin/rgsp-kmsg-start.sh \
            </dev/null >/data/local/tmp/rgsp-kmsg-start.log 2>&1 &
    fi
    sleep 2
fi
pidof rgsp_kmsg_logger
[ -s "$B/RGSP_ANDROID_KMSG_BOUNDED.log" ]
sh "$B/refresh_rgsp_input_live.sh"
sleep 2
dumpsys input > "$BACKUP/input-after.txt"
grep -Fq ': ANBERNIC-keys' "$BACKUP/input-after.txt"
grep -Fq ': axp2202-pek' "$BACKUP/input-after.txt"
grep -Fq ': dierct-keys-polled' "$BACKUP/input-after.txt"
pidof surfaceflinger system_server com.android.systemui com.android.launcher3
sync
echo INPUT_PRECALIBRATION_READY
