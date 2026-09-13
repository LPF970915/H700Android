#!/system/bin/sh
set -eu
test "$(getprop ro.product.device)" = rgsp
state=/data/local/tmp/rgsp-nav-trial-20260913
test ! -e "$state"
umask 077
mkdir "$state"
settings --user 0 get secure enabled_accessibility_services > "$state/services.before"
settings --user 0 get secure accessibility_enabled > "$state/enabled.before"
settings --user 0 get system system_locales > "$state/locales.before"
getprop persist.sys.locale > "$state/locale-property.before"
component=com.roc.rgsp.navtrial/.NavigationService
before=$(cat "$state/services.before")
case "$before" in
    null|'') after=$component ;;
    *) after=$before:$component ;;
esac
printf '%s\n' "$after" > "$state/services.trial"
settings --user 0 put secure enabled_accessibility_services "$after"
settings --user 0 put secure accessibility_enabled 1
echo NAV_TRIAL_ENABLED
