#!/system/bin/sh
# Independent, empty-data feasibility card only. Never used on the release card.
set -eu
[ "$(getprop ro.h700.prototype)" = rg34xxsp-dualabi-gsi10-p1-20261031 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop ro.zygote)" = zygote64_32 ]
[ "$(getprop sys.boot_completed)" = 1 ]
state=/data/local/h700-prototype
mkdir -p "$state"
chmod 0700 "$state"
exec >"$state/setup.log" 2>&1
[ ! -f "$state/complete" ] || exit 0
while read -r package filename abi digest; do
    case "$filename" in H700AbiProbe64.apk|MTManager.apk|RetroArch.apk|PPSSPP.apk) ;; *) exit 2;; esac
    file=/system/etc/h700-prototype/apks/$filename
    [ "$(sha256sum "$file" | cut -d ' ' -f 1)" = "$digest" ]
    pm install -r --abi "$abi" "$file"
    dumpsys package "$package" | grep -F "primaryCpuAbi=$abi"
done </system/etc/h700-prototype/apps.list
settings put global device_provisioned 1
settings --user 0 put secure user_setup_complete 1
settings --user 0 put secure enabled_accessibility_services com.roc.rgsp.navtrial/.NavigationService
settings --user 0 put secure accessibility_enabled 1
pm set-home-activity --user 0 com.overdevs.at4k/.MainActivity
echo PROTOTYPE_APPS_INSTALLED >"$state/complete"
am start -a android.intent.action.MAIN -c android.intent.category.HOME
