#!/system/bin/sh
# Compatibility for older ramdisks; new ROMS-vold ramdisks never mount p8.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(id -u)" = 0 ]
mode=${1:-mount}
case "$mode" in mount|release) ;; *) exit 2 ;; esac
# The BSP's three cached processes starve the SAF/media provider chain.
# Preserve any explicit operator tuning; raise only the unset RGSP default.
if [ "$(device_config get activity_manager max_cached_processes)" = null ]; then
    device_config put activity_manager max_cached_processes 8
fi
state=/data/rgsp-persist
mkdir -p "$state"
chmod 0700 "$state"
if awk '$3=="179:8" && $5=="/rgsp-persist" {found=1} END {exit !found}' /proc/self/mountinfo; then
    stop rgsp-kmsg-bounded
    trap 'start rgsp-kmsg-bounded' EXIT
    tries=0
    while [ "$(getprop init.svc.rgsp-kmsg-bounded)" != stopped ]; do
        tries=$((tries + 1))
        [ "$tries" -le 10 ] || exit 1
        sleep 1
    done
    # Preserve diagnostic evidence without importing commands or provisioning data.
    for name in RGSP_SINGLE_CARD_BOOT.log RGSP_ANDROID_KMSG_BOUNDED.log RGSP_ANDROID_KMSG_BOUNDED.log.1; do
        source=/rgsp-persist/$name
        target=$state/legacy-$name
        [ -f "$source" ] && [ ! -L "$source" ] || continue
        [ ! -e "$target" ] && [ ! -L "$target" ] || continue
        cp -n "$source" "$target"
    done
    sync
    # A busy mount is a failed handoff, never a reason for lazy/forced unmount.
    umount /rgsp-persist
    start rgsp-kmsg-bounded
    trap - EXIT
fi
[ "$mode" != release ] || exit 0
tries=0
while :; do
    volume=$(sm list-volumes all | grep '^public:179,8 ' || true)
    case "$volume" in
        "public:179,8 mounted "*) setprop sys.rgsp.roms ready; exit 0 ;;
        "public:179,8 unmounted "*|"public:179,8 unmountable "*)
            sm mount public:179,8
            break ;;
    esac
    tries=$((tries + 1))
    [ "$tries" -le 30 ] || { setprop sys.rgsp.roms missing; exit 1; }
    sleep 1
done
sm list-volumes all | grep -q '^public:179,8 mounted '
setprop sys.rgsp.roms ready
