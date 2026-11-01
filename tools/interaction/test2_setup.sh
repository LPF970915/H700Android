#!/system/bin/sh
# Fresh, image-owned ARM64 parity inputs; later user choices win.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(id -u)" = 0 ]
[ "$(getprop ro.h700.prototype.image)" = dualabi-parity-test2-20261101 ]
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ]
[ "$(getprop ro.zygote)" = zygote64_32 ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(am get-current-user)" = 0 ]
state=/data/local/h700-parity-test2
umask 077
mkdir -p "$state"
if [ -f "$state/complete" ]; then
    setprop sys.h700.prototype.setup complete
    exit 0
fi
exec 8>"$state/lockfile"
flock -n 8 8>&8 || exit 1
exec >>"$state/setup.log" 2>&1
setprop sys.h700.prototype.setup working
trap 'setprop sys.h700.prototype.setup failed' EXIT
if [ ! -f "$state/defaults" ]; then
    # Known unsupported HCI integration is not retried on every later boot.
    svc bluetooth disable
    settings put global device_provisioned 1
    settings --user 0 put secure user_setup_complete 1
    settings --user 0 put secure show_ime_with_hard_keyboard 1
    leanback=com.android.inputmethod.leanback/.service.LeanbackImeService
    ime list -a -s | grep -Fxq "$leanback"
    ime enable --user 0 "$leanback"
    ime set --user 0 "$leanback"
    component=com.roc.rgsp.navtrial/.NavigationService
    before=$(settings --user 0 get secure enabled_accessibility_services)
    case ":$before:" in
        *":$component:"*) after=$before ;;
        :null:|::) after=$component ;;
        *) after=$before:$component ;;
    esac
    settings --user 0 put secure enabled_accessibility_services "$after"
    settings --user 0 put secure accessibility_enabled 1
    pm set-home-activity --user 0 com.overdevs.at4k/.MainActivity
    touch "$state/defaults"
fi
# This installer verifies every image-owned input and uses its own kernel lock.
# It waits for the protected p8 public-volume handoff; it never formats media.
sh /system/bin/h700-preinstall.sh apply
[ "$(getprop sys.h700.preinstall)" = complete ]
am broadcast --user 0 -n com.roc.rgsp.rotation/.RotationReceiver \
    -a com.roc.rgsp.rotation.PREPARE
am startservice --user 0 -n com.roc.rgsp.lid/.LidService
printf 'ARM64_PARITY_TEST2_DEFAULTS_AND_SEVEN_APPS\n' >"$state/complete.tmp"
mv "$state/complete.tmp" "$state/complete"
setprop sys.h700.prototype.setup complete
trap - EXIT
am start -a android.intent.action.MAIN -c android.intent.category.HOME
