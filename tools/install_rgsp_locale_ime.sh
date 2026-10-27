#!/system/bin/sh
# Exact RGSP framework update; retain and automatically restore the prior JAR.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-locale-ime-20261025
target=/system/framework/services.jar
before=f370b5c4d80eec9e209fc4ed8592a858e2bc2bbfd5947aaadd847a683a86ad18
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
[ ! -L "$target" ]
[ ! -e "$target.rgsp-locale-new" ]
! awk -v p="$target" '$5==p {found=1} END {exit !found}' /proc/self/mountinfo
grep -q '^/dev/mmcblk0p5 / ext4 ro,' /proc/mounts
after=$(cat "$stage/expected.sha256")
case "$after" in *[!a-f0-9]*|'') exit 2 ;; esac
[ "${#after}" = 64 ]
[ "$(sha "$stage/services.before.jar")" = "$before" ]
[ "$(sha "$stage/services.after.jar")" = "$after" ]
[ "$(sha "$target")" = "$before" ]
[ "$(getprop service.adb.tcp.port)" = 5555 ]
[ -f /system/bin/rgsp-wifi-adb-session.sh ] || [ -f /data/local/tmp/rgsp-restore-debug.sh ]

stop_framework() {
    setprop service.adb.tcp.port -1
    stop adbd
    setprop sys.boot_completed 0
    stop zygote
    stop netd
    sleep 2
    [ -z "$(pidof system_server || true)" ]
}
start_framework() { start netd; start zygote; }
restore_debug() {
    if [ -f /system/bin/rgsp-wifi-adb-session.sh ]; then
        sh /system/bin/rgsp-wifi-adb-session.sh
    else sh /data/local/tmp/rgsp-restore-debug.sh
    fi
}
replace_jar() {
    mount -o remount,rw / || return 1
    cp "$1" "$target.rgsp-locale-new" || return 1
    chown 0:0 "$target.rgsp-locale-new" || return 1
    chmod 0644 "$target.rgsp-locale-new" || return 1
    [ "$(sha "$target.rgsp-locale-new")" = "$2" ] || return 1
    mv "$target.rgsp-locale-new" "$target" || return 1
    restorecon "$target" || return 1
    sync || return 1
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
rollback() {
    stop_framework || true
    # Remove only this installer's known temporary output, never user files.
    rm -f "$target.rgsp-locale-new"
    replace_jar "$stage/services.before.jar" "$before" || return 1
    start_framework
    wait_framework || return 1
    restore_debug || return 1
    echo "LOCALE_IME_INSTALL=ROLLED_BACK; SHA=$(sha "$target")"
}
trap 'sync; mount -o remount,ro /' EXIT
if ! stop_framework; then
    start_framework
    if wait_framework; then restore_debug; fi
    exit 1
fi
if ! replace_jar "$stage/services.after.jar" "$after"; then
    rollback
    exit 1
fi
start_framework
if wait_framework; then
    restore_debug
    echo "LOCALE_IME_INSTALL=STABLE; SHA=$(sha "$target")"
    exit 0
fi
rollback
exit 1
