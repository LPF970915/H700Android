#!/system/bin/sh
# One-time provisioning for fresh full-flash data; later user choices win.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(am get-current-user)" = 0 ]
[ "$(id -u)" = 0 ]
state=/data/local/rgsp-navigation
marker=$state/complete-v1
[ ! -f "$marker" ] || { echo 'NAVIGATION=already-provisioned'; exit 0; }
component=com.roc.rgsp.navtrial/.NavigationService
apk=$(pm path com.roc.rgsp.navtrial | sed -n 's/^package://p' | head -n 1)
case "$apk" in /system/app/RGSPNavigation/*) ;; *) exit 1 ;; esac
[ -f "$apk" ]
umask 077
mkdir -p "$state"
mkdir "$state/lock"
trap 'rmdir "$state/lock"' EXIT
before=$(settings --user 0 get secure enabled_accessibility_services)
enabled=$(settings --user 0 get secure accessibility_enabled)
printf '%s\n' "$before" > "$state/services.before"
printf '%s\n' "$enabled" > "$state/enabled.before"
case ":$before:" in
    *":$component:"*) after=$before ;;
    :null:|::) after=$component ;;
    *) after=$before:$component ;;
esac
restore() {
    if [ "$2" = null ]; then
        settings --user 0 delete secure "$1"
    else
        settings --user 0 put secure "$1" "$2"
    fi
}
rollback() {
    rc=$?
    trap - EXIT
    restore enabled_accessibility_services "$before" || true
    restore accessibility_enabled "$enabled" || true
    rmdir "$state/lock"
    exit "$rc"
}
trap rollback EXIT
settings --user 0 put secure enabled_accessibility_services "$after"
settings --user 0 put secure accessibility_enabled 1
[ "$(settings --user 0 get secure enabled_accessibility_services)" = "$after" ]
[ "$(settings --user 0 get secure accessibility_enabled)" = 1 ]
printf 'rgsp-navigation-v1\n' > "$state/complete-v1.tmp"
mv "$state/complete-v1.tmp" "$marker"
trap 'rmdir "$state/lock"' EXIT
echo 'NAVIGATION=provisioned'
