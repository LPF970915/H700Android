#!/system/bin/sh
set -eu
test "$(getprop ro.product.device)" = rgsp
state=/data/local/tmp/rgsp-display-test-20260913
test -f "$state/timeout.before"
test -f "$state/stayon.before"
test "$(settings get system screen_off_timeout)" = 2147483647
test "$(settings get global stay_on_while_plugged_in)" = 7
restore() {
    table=$1
    key=$2
    value=$(cat "$3")
    if [ "$value" = null ]; then
        settings delete "$table" "$key"
    else
        settings put "$table" "$key" "$value"
    fi
}
restore system screen_off_timeout "$state/timeout.before"
restore global stay_on_while_plugged_in "$state/stayon.before"
echo TEST_DISPLAY_SETTINGS_RESTORED
