#!/system/bin/sh
# Replace only this RGSP's validated A-unlock SystemUI; retain exact rollback.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-power-ui-20261025
target=/system/product/priv-app/SystemUI/SystemUI.apk
before=d83ba4fb106c5a3e4ddb3e1d6183572e49a6af44806f1e7c78d26a71f3ebce89
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
after=$(cat "$stage/expected.sha256")
case "$after" in *[!a-f0-9]*|'') exit 2 ;; esac
[ "${#after}" = 64 ]
case "${1:-}" in
    install) source=$stage/SystemUI.after.apk; expected=$before; replacement=$after ;;
    rollback) source=$stage/SystemUI.before.apk; expected=$after; replacement=$before ;;
    *) exit 2 ;;
esac
[ "$(sha "$stage/SystemUI.before.apk")" = "$before" ]
[ "$(sha "$source")" = "$replacement" ]
[ "$(sha "$target")" = "$expected" ]
[ ! -L "$target" ]
[ ! -e "$target.rgsp-power-new" ]
! awk -v p="$target" '$5==p {found=1} END {exit !found}' /proc/self/mountinfo
grep -q '^/dev/mmcblk0p5 / ext4 ro,' /proc/mounts
mount -o remount,rw /
finish() {
    rc=$?; trap - EXIT; sync
    mount -o remount,ro / || rc=1
    echo "POWER_UI_INSTALL_EXIT=$rc"; exit "$rc"
}
trap finish EXIT
cp "$source" "$target.rgsp-power-new"
chown 0:0 "$target.rgsp-power-new"
chmod 0644 "$target.rgsp-power-new"
[ "$(sha "$target.rgsp-power-new")" = "$replacement" ]
mv "$target.rgsp-power-new" "$target"
restorecon "$target"
sync
ui_pid=$(pidof com.android.systemui)
[ -n "$ui_pid" ]
[ "$(tr -d '\000' < /proc/$ui_pid/cmdline)" = com.android.systemui ]
kill -TERM "$ui_pid"
sleep 3
mount -o remount,ro /
echo "SYSTEMUI_REPLACED=$replacement; exact rollback retained"
