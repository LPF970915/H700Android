#!/system/bin/sh
# Persist the validated framework/feature pair, or restore its exact original files.
set -eu
export PATH=/system/bin:/vendor/bin
audit_stage=/data/local/tmp/rgsp-settings-services-20261023
target=/system/framework/services.jar
feature=/vendor/etc/permissions/android.hardware.usb.host.xml
before=299d97f020f97ca4bfc400773870983f52df8fa8b036ae245640cdad58b04413
after=f370b5c4d80eec9e209fc4ed8592a858e2bc2bbfd5947aaadd847a683a86ad18
feature_sha=201da252a1ed52d5d1019412900d7a1cb530afb4558f9f1ba3d124189a1f9819
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

stop_framework() {
    setprop service.adb.tcp.port -1
    stop adbd
    setprop sys.boot_completed 0
    stop zygote
    stop netd
    sleep 2
}

replace_file() {
    source=$1 destination=$2 expected=$3
    [ ! -L "$destination" ]
    [ ! -e "$destination.rgsp-services-new" ]
    cp "$source" "$destination.rgsp-services-new"
    chown 0:0 "$destination.rgsp-services-new"
    chmod 0644 "$destination.rgsp-services-new"
    [ "$(file_sha "$destination.rgsp-services-new")" = "$expected" ]
    mv "$destination.rgsp-services-new" "$destination"
    restorecon "$destination"
    [ "$(file_sha "$destination")" = "$expected" ]
}

abort_preparation() {
    start netd
    start zygote
    nohup sh "$0" watch-rollback > "$audit_stage/preparation-recovery.log" 2>&1 < /dev/null &
    echo PREPARATION_FAILED_NO_PERSISTENT_FILES_WRITTEN >&2
    exit 1
}

case "${1:-}" in
watch-install|watch-rollback)
    action=$1
    attempts=0
    while [ "$attempts" -lt 90 ]; do
        sleep 2
        if [ "$(getprop sys.boot_completed)" = 1 ]; then
            if [ "$action" = watch-rollback ] ||
                { service check usb | grep -q ': found' && service check oem_lock | grep -q ': found'; }; then
                restore_transport
                pidof system_server > "$audit_stage/$action-healthy"
                echo "$action=HEALTHY"
                exit 0
            fi
        fi
        attempts=$((attempts + 1))
    done
    if [ "$action" = watch-install ]; then
        echo AUTOMATIC_ROLLBACK
        exec sh "$0" rollback
    fi
    echo ROLLBACK_FRAMEWORK_NOT_READY >&2
    exit 1
    ;;
install)
    [ -f "$audit_stage/trial-mounted" ]
    [ -f "$audit_stage/trial-validated" ]
    [ "$(file_sha "$target")" = "$after" ]
    [ "$(file_sha "$audit_stage/services.jar")" = "$after" ]
    [ "$(file_sha "$audit_stage/android.hardware.usb.host.xml")" = "$feature_sha" ]
    [ ! -e "$target.rgsp-services-new" ]
    [ ! -e "$feature.rgsp-services-new" ]
    stop_framework
    umount "$target" || umount -l "$target" || abort_preparation
    umount /vendor/etc/permissions || umount -l /vendor/etc/permissions || abort_preparation
    [ "$(file_sha "$target")" = "$before" ] || abort_preparation
    [ ! -e "$feature" ] || abort_preparation
    next_action=watch-install
    ;;
rollback)
    [ "$(file_sha "$target")" = "$after" ]
    [ "$(file_sha "$feature")" = "$feature_sha" ]
    stop_framework
    next_action=watch-rollback
    ;;
*) echo 'Use install or rollback' >&2; exit 2;;
esac

finish() {
    rc=$?
    trap - EXIT
    if [ "$rc" != 0 ]; then
        # Both originals are verified; revert a partially completed two-file update.
        rm -f "$target.rgsp-services-new" "$feature.rgsp-services-new"
        replace_file "$audit_stage/services.before.jar" "$target" "$before" || true
        if [ -e "$feature" ] && [ "$(file_sha "$feature")" = "$feature_sha" ]; then
            rm "$feature"
        fi
        next_action=watch-rollback
    fi
    sync
    mount -o remount,ro /vendor || rc=1
    mount -o remount,ro / || rc=1
    start netd
    start zygote
    nohup sh "$0" "$next_action" > "$audit_stage/$next_action.log" 2>&1 < /dev/null &
    echo "SETTINGS_SERVICES_INSTALL_EXIT=$rc"
    exit "$rc"
}
trap finish EXIT
mount -o remount,rw /
mount -o remount,rw /vendor
if [ "$next_action" = watch-install ]; then
    replace_file "$audit_stage/services.jar" "$target" "$after"
    replace_file "$audit_stage/android.hardware.usb.host.xml" "$feature" "$feature_sha"
    mv "$audit_stage/trial-mounted" "$audit_stage/trial-completed"
    echo SETTINGS_SERVICES_PERSISTED
else
    replace_file "$audit_stage/services.before.jar" "$target" "$before"
    rm "$feature"
    echo SETTINGS_SERVICES_ORIGINALS_RESTORED
fi
