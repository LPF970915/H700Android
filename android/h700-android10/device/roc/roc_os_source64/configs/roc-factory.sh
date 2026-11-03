#!/system/bin/sh
# Pure-system defaults, once per clean userdata. Never installs a third-party APK.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ]
[ "$(getprop ro.roc.source64.round)" = 2 ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(am get-current-user)" = 0 ]
state=/data/local/roc-factory-v1
umask 077
mkdir -p "$state"
exec 8>"$state/lockfile"
flock -n 8 8>&8 || exit 0
[ ! -f "$state/complete" ] || exit 0
leanback=com.android.inputmethod.leanback/.service.LeanbackImeService
nav=com.roc.rgsp.navtrial/.NavigationService
apk=$(pm path com.android.inputmethod.leanback | sed -n 's/^package://p' | head -n 1)
[ -f "$apk" ]
[ "$(sha256sum "$apk" | cut -d ' ' -f 1)" = "$(cat /system/etc/rgsp/leanback.sha256)" ]
ime list -a -s | grep -Fxq "$leanback"
ime enable --user 0 "$leanback"
ime set --user 0 "$leanback"
[ "$(settings --user 0 get secure default_input_method)" = "$leanback" ]
settings --user 0 put secure show_ime_with_hard_keyboard 1
settings --user 0 put global device_provisioned 1
settings --user 0 put secure user_setup_complete 1
# The preferred HOME XML handles the first HOME intent. Reassert only until complete.
pm path com.overdevs.at4k | grep -q '^package:'
pm set-home-activity --user 0 com.overdevs.at4k/.MainActivity
home=$(cmd package resolve-activity --brief --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1)
[ "$home" = com.overdevs.at4k/.MainActivity ]
services=$(settings --user 0 get secure enabled_accessibility_services)
case ":$services:" in *":$nav:"*) ;; :null:|::) services=$nav ;; *) services=$services:$nav ;; esac
settings --user 0 put secure enabled_accessibility_services "$services"
settings --user 0 put secure accessibility_enabled 1
[ "$(settings --user 0 get secure enabled_accessibility_services)" = "$services" ]
[ "$(settings --user 0 get secure accessibility_enabled)" = 1 ]
printf 'roc-source64-pure-v1\n' > "$state/complete.tmp"
mv "$state/complete.tmp" "$state/complete"
