#!/system/bin/sh
# Resume the one documented interrupted transaction, without touching user data.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-foundation-align-20261027
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
provider=/system/priv-app/SettingsProvider/SettingsProvider.apk
framework=/system/framework/framework-res.apk
pb=cbb741d64fe482015f3cd484ed7e3ffd1e77ab548ea1c70a35b9d29bef68d1b1
pa=1a39ff436dafdaa0bd4dcaf1148959eb7cd47532dc39a3fe82d0f2984ffa67bf
fb=37d1189901ffbe03c3a0502c105be2ec8fe1fd9918cbd6af950ab47949485a88
fa=a8e4d04bdc7a37120c143a781204d9166cd76c96f108f52cc2d789884f5d3d86
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(sha "$provider")" = "$pb" ]
[ "$(sha "$framework")" = "$fa" ]
[ -z "$(pidof system_server || true)" ]
[ -z "$(pidof zygote || true)" ]
[ "$(sha "$stage/SettingsProvider.before.apk")" = "$pb" ]
[ "$(sha "$stage/SettingsProvider.candidate.apk")" = "$pa" ]
[ "$(sha "$stage/framework-res.before.apk")" = "$fb" ]
[ "$(sha "$stage/framework-res.candidate.apk")" = "$fa" ]
write_apk() {
    mount -o remount,rw / || return 1
    cp "$1" "$2.rgsp-foundation-new" || return 1
    chmod 0644 "$2.rgsp-foundation-new" || return 1
    chown 0:0 "$2.rgsp-foundation-new" || return 1
    [ "$(sha "$2.rgsp-foundation-new")" = "$3" ] || return 1
    mv "$2.rgsp-foundation-new" "$2" || return 1
    restorecon "$2" || return 1
}
stop_all() { stop adbd; stop zygote; stop netd; stop bootanim; sleep 2; }
start_all() { start netd; start zygote; }
wait_stable() {
    deadline=$(( $(cut -d . -f 1 /proc/uptime) + 180 ))
    previous=; stable=0
    while [ "$(cut -d . -f 1 /proc/uptime)" -lt "$deadline" ]; do
        current=$(pidof system_server || true):$(pidof com.android.systemui || true)
        if [ "$(getprop sys.boot_completed)" = 1 ] && [ -n "$(pidof system_server || true)" ] &&
                [ -n "$(pidof com.android.systemui || true)" ]; then
            if [ "$current" = "$previous" ]; then stable=$((stable+1)); else stable=0; fi
            [ "$stable" -lt 5 ] || return 0
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
    stop_all
    write_apk "$stage/SettingsProvider.before.apk" "$provider" "$pb"
    write_apk "$stage/framework-res.before.apk" "$framework" "$fb"
    stop bootanim
    sync
    mount -o remount,ro /
    start_all
    wait_stable
    restore_debug
    echo FOUNDATION_RECOVERY=ROLLED_BACK
}
trap 'sync; mount -o remount,ro /' EXIT
stop bootanim
sleep 1
if ! write_apk "$stage/SettingsProvider.candidate.apk" "$provider" "$pa"; then
    rollback
    exit 1
fi
stop bootanim
sync
if ! mount -o remount,ro /; then
    rollback
    exit 1
fi
start_all
if ! wait_stable; then
    rollback
    exit 1
fi
restore_debug
[ "$(sha "$provider")" = "$pa" ]
[ "$(sha "$framework")" = "$fa" ]
grep -q '^/dev/mmcblk0p5 / ext4 ro,' /proc/mounts
echo FOUNDATION_RECOVERY=STABLE_BOTH_CANDIDATES_SYSTEM_RO
