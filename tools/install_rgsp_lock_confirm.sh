#!/system/bin/sh
# Persist/roll back the physically scoped SystemUI fix after a live bind trial.
set -eu
export PATH=/system/bin:/vendor/bin
target=/system/product/priv-app/SystemUI/SystemUI.apk
original=/data/local/tmp/rgsp-a-unlock-20261023/SystemUI.before.apk
candidate=/data/local/tmp/SystemUI.a-unlock-20261023.apk
before=5b4fa0a16dd502df673c8b4abbdae54452b47ea46c7d86df39020cabd1a373b4
after=d83ba4fb106c5a3e4ddb3e1d6183572e49a6af44806f1e7c78d26a71f3ebce89
file_sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
[ "$(file_sha "$original")" = "$before" ]
case "${1:-}" in
    install) source=$candidate; expected=$before; replacement=$after ;;
    rollback) source=$original; expected=$after; replacement=$before ;;
    *) echo 'Use install or rollback' >&2; exit 2 ;;
esac
[ "$(file_sha "$source")" = "$replacement" ]
[ "$(file_sha "$target")" = "$expected" ]
[ ! -L "$target" ]
[ ! -e "$target.rgsp-a-unlock-new" ]
# Refuse any still-attached trial overlay and an unexpected writable root.
! awk -v p="$target" '$5==p {found=1} END {exit !found}' /proc/self/mountinfo
grep -q '^/dev/mmcblk0p5 / ext4 ro,' /proc/mounts
mount -o remount,rw /
finish() {
    rc=$?
    trap - EXIT
    sync
    mount -o remount,ro / || rc=1
    echo "SYSTEMUI_INSTALL_EXIT=$rc"
    exit "$rc"
}
trap finish EXIT
cp "$source" "$target.rgsp-a-unlock-new"
chown 0:0 "$target.rgsp-a-unlock-new"
chmod 0644 "$target.rgsp-a-unlock-new"
[ "$(file_sha "$target.rgsp-a-unlock-new")" = "$replacement" ]
mv "$target.rgsp-a-unlock-new" "$target"
restorecon "$target"
[ "$(file_sha "$target")" = "$replacement" ]
sync
ui_pid=$(pidof com.android.systemui)
[ "$(tr -d '\000' < /proc/$ui_pid/cmdline)" = com.android.systemui ]
kill -TERM "$ui_pid"
sleep 3
pidof com.android.systemui
sha256sum "$target"
echo "SYSTEMUI_$1=OK"
