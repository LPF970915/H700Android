#!/system/bin/sh
# Exact-module graphics trial with automatic byte-for-byte rollback on startup failure.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-hwc-timing-20261025
target=/vendor/lib/hw/hwcomposer.cupid.so
before=89a1f16c3b2b03b3f3250c77f1cae3d35a9995a44281a7538307d8fbbb7fecf2
after=eac4cb95cdcdc76705e1e76b2b8d6f3ca4fe3bbf1047161f45a7361b59802698
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
[ ! -L "$target" ]
[ ! -e "$target.rgsp-timing-new" ]
! awk -v p="$target" '$5==p {found=1} END {exit !found}' /proc/self/mountinfo
grep -q '^/dev/mmcblk0p6 /vendor ext4 ro,' /proc/mounts
[ "$(sha "$stage/hwcomposer.before.so")" = "$before" ]
[ "$(sha "$stage/hwcomposer.after.so")" = "$after" ]
[ "$(getprop service.adb.tcp.port)" = 5555 ]
[ -f /system/bin/rgsp-wifi-adb-session.sh ] || [ -f /data/local/tmp/rgsp-restore-debug.sh ]
case "${1:-}" in
    install) source=$stage/hwcomposer.after.so; expected=$before; replacement=$after ;;
    rollback) source=$stage/hwcomposer.before.so; expected=$after; replacement=$before ;;
    *) exit 2 ;;
esac
[ "$(sha "$target")" = "$expected" ]

stop_graphics() {
    # netd can restart with zygote and rebuild its firewall chains.
    # Close TCP debugging first; reopen only after source guards are restored.
    setprop service.adb.tcp.port -1
    stop adbd
    setprop sys.boot_completed 0
    stop zygote
    stop netd
    stop surfaceflinger
    stop vendor.hwcomposer-2-2
}
start_graphics() {
    start netd
    start vendor.hwcomposer-2-2
    start surfaceflinger
    start zygote
}
replace_module() {
    mount -o remount,rw /vendor || return 1
    trap 'sync; mount -o remount,ro /vendor' EXIT
    cp "$1" "$target.rgsp-timing-new" || return 1
    chown 0:0 "$target.rgsp-timing-new" || return 1
    chmod 0644 "$target.rgsp-timing-new" || return 1
    [ "$(sha "$target.rgsp-timing-new")" = "$2" ] || return 1
    mv "$target.rgsp-timing-new" "$target" || return 1
    restorecon "$target" || return 1
    sync || return 1
    mount -o remount,ro /vendor || return 1
    trap - EXIT
}
restore_debug() {
    if [ -f /system/bin/rgsp-wifi-adb-session.sh ]; then
        sh /system/bin/rgsp-wifi-adb-session.sh
    else sh /data/local/tmp/rgsp-restore-debug.sh
    fi
}
wait_framework() {
    deadline=$(( $(cut -d . -f 1 /proc/uptime) + 180 ))
    previous_pids=; stable=0
    while [ "$(cut -d . -f 1 /proc/uptime)" -lt "$deadline" ]; do
        sf=$(pidof surfaceflinger || true)
        composer=$(pidof android.hardware.graphics.composer@2.2-service || true)
        ui=$(pidof com.android.systemui || true)
        pids=$sf:$composer:$ui
        if [ "$(getprop sys.boot_completed)" = 1 ] && [ -n "$sf" ] && [ -n "$composer" ] && [ -n "$ui" ]; then
            if [ "$pids" = "$previous_pids" ]; then stable=$((stable+1)); else stable=0; fi
            [ "$stable" -lt 5 ] || { echo "GRAPHICS_STABLE=$pids"; return 0; }
        else stable=0
        fi
        previous_pids=$pids
        sleep 2
    done
    return 1
}
stop_graphics
if ! replace_module "$source" "$replacement"; then
    echo HWC_REPLACEMENT_FAILED >&2
    if [ "$(sha "$target")" = "$after" ]; then
        replace_module "$stage/hwcomposer.before.so" "$before" || true
    fi
    sync
    mount -o remount,ro /vendor || true
    start_graphics
    if wait_framework; then restore_debug; fi
    exit 1
fi
start_graphics
if wait_framework; then
    restore_debug
    echo "HWC_$1=STABLE; SHA=$(sha "$target")"
    exit 0
fi
if [ "$1" = install ]; then
    echo HWC_STARTUP_TIMEOUT_ROLLING_BACK >&2
    stop_graphics
    replace_module "$stage/hwcomposer.before.so" "$before"
    start_graphics
    if wait_framework; then restore_debug; fi
    echo "HWC_INSTALL=ROLLED_BACK; SHA=$(sha "$target")"
else echo HWC_ROLLBACK_STARTUP_TIMEOUT >&2
fi
exit 1
