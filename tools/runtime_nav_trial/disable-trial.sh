#!/system/bin/sh
set -eu
state=/data/local/tmp/rgsp-nav-trial-20260913
test "$(getprop ro.product.device)" = rgsp
test -f "$state/services.before"
current=$(settings --user 0 get secure enabled_accessibility_services)
expected=$(cat "$state/services.trial")
test "$current" = "$expected" || {
    echo "Accessibility settings changed since trial; review before restoring."
    exit 40
}
restore() {
    key=$1
    value=$(cat "$2")
    if [ "$value" = null ]; then
        settings --user 0 delete secure "$key"
    else
        settings --user 0 put secure "$key" "$value"
    fi
}
restore enabled_accessibility_services "$state/services.before"
restore accessibility_enabled "$state/enabled.before"
am force-stop com.roc.rgsp.navtrial
echo NAV_TRIAL_DISABLED_SETTINGS_RESTORED
