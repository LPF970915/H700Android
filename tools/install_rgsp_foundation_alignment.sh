#!/system/bin/sh
# Align exactly two reviewed resource APKs; preserve data and rollback on failure.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-foundation-align-20261027
provider=/system/priv-app/SettingsProvider/SettingsProvider.apk
framework=/system/framework/framework-res.apk
provider_before=cbb741d64fe482015f3cd484ed7e3ffd1e77ab548ea1c70a35b9d29bef68d1b1
provider_after=1a39ff436dafdaa0bd4dcaf1148959eb7cd47532dc39a3fe82d0f2984ffa67bf
framework_before=37d1189901ffbe03c3a0502c105be2ec8fe1fd9918cbd6af950ab47949485a88
framework_after=a8e4d04bdc7a37120c143a781204d9166cd76c96f108f52cc2d789884f5d3d86
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
grep -q '^/dev/mmcblk0p5 / ext4 ro,' /proc/mounts
for name in SettingsProvider framework-res; do
    [ -f "$stage/$name.before.apk" ]
    [ -f "$stage/$name.candidate.apk" ]
done
[ "$(sha "$provider")" = "$provider_before" ]
[ "$(sha "$framework")" = "$framework_before" ]
[ "$(sha "$stage/SettingsProvider.before.apk")" = "$provider_before" ]
[ "$(sha "$stage/SettingsProvider.candidate.apk")" = "$provider_after" ]
[ "$(sha "$stage/framework-res.before.apk")" = "$framework_before" ]
[ "$(sha "$stage/framework-res.candidate.apk")" = "$framework_after" ]
for target in "$provider" "$framework"; do
    [ ! -L "$target" ]
    [ ! -e "$target.rgsp-foundation-new" ]
    ! awk -v p="$target" '$5==p {found=1} END {exit !found}' /proc/self/mountinfo
done
stop_framework() {
    setprop service.adb.tcp.port -1
    stop adbd
    setprop sys.boot_completed 0
    stop zygote
    stop netd
    stop bootanim
    sleep 2
    [ -z "$(pidof system_server || true)" ]
}
start_framework() { start netd; start zygote; }
replace_apk() {
    source=$1; target=$2; expected=$3
    mount -o remount,rw / || return 1
    cp "$source" "$target.rgsp-foundation-new" || return 1
    chmod 0644 "$target.rgsp-foundation-new" || return 1
    chown 0:0 "$target.rgsp-foundation-new" || return 1
    [ "$(sha "$target.rgsp-foundation-new")" = "$expected" ] || return 1
    mv "$target.rgsp-foundation-new" "$target" || return 1
    restorecon "$target" || return 1
    sync || return 1
    # SurfaceFlinger can start bootanimation as zygote stops. It maps
    # framework-res.apk; an open deleted inode prevents an ext4 RO remount.
    stop bootanim
    mount -o remount,ro / || return 1
}
wait_framework() {
    deadline=$(( $(cut -d . -f 1 /proc/uptime) + 180 ))
    previous=; stable=0
    while [ "$(cut -d . -f 1 /proc/uptime)" -lt "$deadline" ]; do
        server=$(pidof system_server || true); ui=$(pidof com.android.systemui || true)
        current=$server:$ui
        if [ "$(getprop sys.boot_completed)" = 1 ] && [ -n "$server" ] && [ -n "$ui" ] &&
                service check usb | grep -q ': found' && service check oem_lock | grep -q ': found'; then
            if [ "$current" = "$previous" ]; then stable=$((stable+1)); else stable=0; fi
            [ "$stable" -lt 5 ] || { echo "FRAMEWORK_STABLE=$current"; return 0; }
        else stable=0
        fi
        previous=$current; sleep 2
    done
    return 1
}
restore_debug() {
    if [ -f /system/bin/rgsp-wifi-adb-session.sh ]; then sh /system/bin/rgsp-wifi-adb-session.sh
    else sh /data/local/tmp/rgsp-restore-debug.sh
    fi
}
rollback() {
    stop_framework || true
    rm -f "$provider.rgsp-foundation-new" "$framework.rgsp-foundation-new"
    replace_apk "$stage/SettingsProvider.before.apk" "$provider" "$provider_before" || return 1
    replace_apk "$stage/framework-res.before.apk" "$framework" "$framework_before" || return 1
    start_framework
    wait_framework || return 1
    restore_debug || return 1
    echo FOUNDATION_ALIGNMENT=ROLLED_BACK
}
trap 'sync; mount -o remount,ro /' EXIT
if ! stop_framework; then
    start_framework
    if wait_framework; then restore_debug; fi
    exit 1
fi
if ! replace_apk "$stage/SettingsProvider.candidate.apk" "$provider" "$provider_after" ||
        ! replace_apk "$stage/framework-res.candidate.apk" "$framework" "$framework_after"; then
    rollback
    exit 1
fi
start_framework
if wait_framework; then
    restore_debug
    [ "$(sha "$provider")" = "$provider_after" ]
    [ "$(sha "$framework")" = "$framework_after" ]
    grep -q '^/dev/mmcblk0p5 / ext4 ro,' /proc/mounts
    echo FOUNDATION_ALIGNMENT=STABLE
    exit 0
fi
rollback
exit 1
