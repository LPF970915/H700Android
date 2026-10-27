#!/system/bin/sh
# Trial/persist the RGSP explicit-port daemon under UART control.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-adbd-optin-20261023
target=/system/bin/adbd
trial_file=/system/bin/adbd.rgsp-trial-20261023
before=10df8fc058054ebdc44eb9aae6800d4996fbac42ad78d6e2b1ac1c47af02c1a7
file_sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
after=$(cat "$stage/after.sha256")
[ "${#after}" = 64 ]
case "$after" in *[!0-9a-f]*) exit 2;; esac
[ "$(file_sha "$stage/adbd.new")" = "$after" ]
[ "$(file_sha "$stage/adbd.before")" = "$before" ]

restore_debug() { sh /data/local/tmp/rgsp-restore-debug.sh; }
discard_trial() {
    if [ -f "$trial_file" ]; then
        [ "$(file_sha "$trial_file")" = "$after" ]
        rm "$trial_file"
    fi
}
undo_trial() {
    stop adbd
    if grep -q ' /system/bin/adbd ' /proc/self/mountinfo; then umount "$target"; fi
    mount -o remount,rw /
    discard_trial
    mount -o remount,ro /
    restore_debug
}
listening() {
    awk '$2 ~ /:15B3$/ && $4 == "0A" {found=1} END {exit !found}' /proc/net/tcp /proc/net/tcp6
}
replace_file() {
    source=$1 expected=$2
    [ ! -L "$target" ]
    [ ! -e "$target.rgsp-new" ]
    cp "$source" "$target.rgsp-new"
    chown 0:2000 "$target.rgsp-new"
    chmod 0755 "$target.rgsp-new"
    restorecon "$target.rgsp-new"
    [ "$(file_sha "$target.rgsp-new")" = "$expected" ]
    mv "$target.rgsp-new" "$target"
    restorecon "$target"
    [ "$(file_sha "$target")" = "$expected" ]
}

case "${1:-}" in
trial)
    [ "$(file_sha "$target")" = "$before" ]
    [ ! -e "$trial_file" ]
    trap undo_trial EXIT
    mount -o remount,rw /
    cp "$stage/adbd.new" "$trial_file"
    chown 0:2000 "$trial_file"
    chmod 0755 "$trial_file"
    chcon u:object_r:adbd_exec:s0 "$trial_file"
    [ "$(file_sha "$trial_file")" = "$after" ]
    mount -o remount,ro /
    stop adbd
    mount -o bind "$trial_file" "$target"
    setprop service.adb.tcp.port -1
    start adbd
    sleep 2
    if [ -z "$(pidof adbd)" ] || listening; then
        echo ADBD_TRIAL_FAILED >&2
        exit 1
    fi
    [ "$(file_sha /proc/$(pidof adbd)/exe)" = "$after" ]
    echo NO_IMPLICIT_TCP_LISTENER_VERIFIED
    [ -z "$(getprop persist.adb.tcp.port)" ]
    stop adbd
    setprop service.adb.tcp.port ''
    start adbd
    sleep 2
    [ -n "$(pidof adbd)" ]
    if listening; then echo EMPTY_PORT_STILL_LISTENING >&2; exit 1; fi
    echo EMPTY_PORT_NO_TCP_LISTENER_VERIFIED
    restore_debug
    sleep 1
    listening
    touch "$stage/trial-ok"
    trap - EXIT
    echo EXPLICIT_GUARDED_TCP_LISTENER_VERIFIED
    ;;
persist)
    [ -f "$stage/trial-ok" ]
    [ "$(file_sha "$target")" = "$after" ]
    grep -q ' /system/bin/adbd ' /proc/self/mountinfo
    stop adbd
    trap 'mount -o remount,ro /; restore_debug' EXIT
    mount -o remount,rw /
    umount "$target"
    [ "$(file_sha "$target")" = "$before" ]
    replace_file "$stage/adbd.new" "$after"
    discard_trial
    mount -o remount,ro /
    trap - EXIT
    restore_debug
    echo ADBD_OPTIN_PERSISTED
    ;;
rollback)
    current=$(file_sha "$target")
    [ "$current" = "$after" ] || [ "$current" = "$before" ]
    stop adbd
    if grep -q ' /system/bin/adbd ' /proc/self/mountinfo; then umount "$target"; fi
    trap 'mount -o remount,ro /; restore_debug' EXIT
    mount -o remount,rw /
    replace_file "$stage/adbd.before" "$before"
    discard_trial
    mount -o remount,ro /
    trap - EXIT
    restore_debug
    echo ORIGINAL_ADBD_RESTORED_GUARDED
    ;;
*) echo 'Use trial, persist or rollback' >&2; exit 2;;
esac
