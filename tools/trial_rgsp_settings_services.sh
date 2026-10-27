#!/system/bin/sh
# Reversible framework trial. No block devices, FRP storage, or boot files are written.
set -eu
export PATH=/system/bin:/vendor/bin
audit_stage=/data/local/tmp/rgsp-settings-services-20261023
target=/system/framework/services.jar
before=299d97f020f97ca4bfc400773870983f52df8fa8b036ae245640cdad58b04413
file_sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
[ "$(file_sha "$audit_stage/services.before.jar")" = "$before" ]

restore_transport() {
    iptables -C INPUT -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP 2>/dev/null ||
        iptables -I INPUT 1 -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP
    ip6tables -C INPUT -p tcp --dport 5555 -j DROP 2>/dev/null ||
        ip6tables -I INPUT 1 -p tcp --dport 5555 -j DROP
    setprop service.adb.tcp.port 5555
    stop adbd
    start adbd
}

restart_framework() {
    # A fresh system_server reuses network IDs from 100; netd must not retain old IDs.
    setprop service.adb.tcp.port -1
    stop adbd
    setprop sys.boot_completed 0
    stop zygote
    stop netd
    sleep 1
    start netd
    start zygote
}

rollback_trial() {
    stop zygote
    sleep 2
    umount "$target" || umount -l "$target"
    umount /vendor/etc/permissions || umount -l /vendor/etc/permissions
    [ "$(file_sha "$target")" = "$before" ]
    restart_framework
    attempts=0
    while [ "$(getprop sys.boot_completed)" != 1 ] && [ "$attempts" -lt 90 ]; do
        sleep 2
        attempts=$((attempts + 1))
    done
    [ "$(getprop sys.boot_completed)" = 1 ] && restore_transport
    echo TRIAL_ROLLED_BACK
}

case "${1:-}" in
watch)
    attempts=0
    while [ "$attempts" -lt 90 ]; do
        sleep 2
        if [ "$(getprop sys.boot_completed)" = 1 ] &&
            service check usb | grep -q ': found' &&
            service check oem_lock | grep -q ': found'; then
            restore_transport
            pidof system_server > "$audit_stage/trial-healthy"
            echo SETTINGS_SERVICES_TRIAL_HEALTHY
            exit 0
        fi
        attempts=$((attempts + 1))
    done
    echo TRIAL_WATCHDOG_ROLLBACK
    rollback_trial
    ;;
rollback)
    [ -f "$audit_stage/trial-mounted" ]
    rollback_trial
    ;;
trial)
    [ "$(file_sha "$target")" = "$before" ]
    [ ! -e /vendor/etc/permissions/android.hardware.usb.host.xml ]
    [ ! -f "$audit_stage/trial-mounted" ]
    after=$(tr -d '\r\n' < "$audit_stage/services.after.sha256")
    [ "${#after}" = 64 ]
    case "$after" in *[!0-9a-f]*) exit 2;; esac
    [ "$(file_sha "$audit_stage/services.jar")" = "$after" ]
    [ "$(file_sha "$audit_stage/android.hardware.usb.host.xml")" = 201da252a1ed52d5d1019412900d7a1cb530afb4558f9f1ba3d124189a1f9819 ]
    mkdir "$audit_stage/permissions"
    cp -a /vendor/etc/permissions/. "$audit_stage/permissions/"
    cp "$audit_stage/android.hardware.usb.host.xml" "$audit_stage/permissions/"
    chmod 0644 "$audit_stage/permissions/android.hardware.usb.host.xml"
    mount -o bind "$audit_stage/services.jar" "$target"
    if ! mount -o bind "$audit_stage/permissions" /vendor/etc/permissions; then
        umount "$target"
        exit 1
    fi
    touch "$audit_stage/trial-mounted"
    pidof system_server > "$audit_stage/system-server-before"
    nohup sh "$0" watch > "$audit_stage/watchdog.log" 2>&1 < /dev/null &
    restart_framework
    echo SETTINGS_SERVICES_TRIAL_STARTED
    ;;
*) echo 'Use trial, rollback or watch' >&2; exit 2;;
esac
