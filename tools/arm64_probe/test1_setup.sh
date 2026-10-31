#!/system/bin/sh
# Fresh test1 image only. Inputs are image-owned; never seed ROM/account/save data.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.h700.prototype.image)" = dualabi-test1-20261031 ]
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ]
[ "$(getprop ro.zygote)" = zygote64_32 ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(id -u)" = 0 ]
state=/data/local/h700-prototype
src=/system/etc/h700-prototype
mkdir -p "$state"
chmod 0700 "$state"
[ ! -f "$state/complete" ] || exit 0
exec 8>"$state/lockfile"
flock -n 8 8>&8 || exit 1
exec >>"$state/setup.log" 2>&1
setprop sys.h700.prototype.setup working
# Known missing HCI integration is deferred; keep this test image's radio off.
svc bluetooth disable
while read -r package filename abi digest; do
    case "$filename" in H700AbiProbe64.apk|MTManager.apk|RetroArch.apk|PPSSPP.apk) ;; *) exit 2;; esac
    file=$src/apks/$filename
    [ "$(sha256sum "$file" | cut -d ' ' -f 1)" = "$digest" ]
    installed=$(pm path "$package" | sed -n 's/^package://p' | head -n 1)
    if [ -z "$installed" ]; then
        pm install -r --abi "$abi" "$file"
        installed=$(pm path "$package" | sed -n 's/^package://p' | head -n 1)
    fi
    [ -f "$installed" ]
    [ "$(sha256sum "$installed" | cut -d ' ' -f 1)" = "$digest" ]
    dumpsys package "$package" | grep -F "primaryCpuAbi=$abi"
done <"$src/apps.list"

for package in com.retroarch.ra32 org.ppsspp.ppsspp; do
    pm grant "$package" android.permission.READ_EXTERNAL_STORAGE
    pm grant "$package" android.permission.WRITE_EXTERNAL_STORAGE
done
ra=/data/user/0/com.retroarch.ra32
uid=$(stat -c %u "$ra")
case "$uid" in ''|*[!0-9]*) exit 3;; esac
[ "$uid" -ge 10000 ]
mkdir -p "$ra/autoconfig/android" "$ra/cores"
if [ ! -e "$ra/autoconfig/android/H700_ANBERNIC_keys.cfg" ]; then
    cp "$src/H700_ANBERNIC_keys.cfg" "$ra/autoconfig/android/H700_ANBERNIC_keys.cfg"
fi
chown -R "$uid:$uid" "$ra/autoconfig" "$ra/cores"
chmod 0700 "$ra/autoconfig" "$ra/autoconfig/android" "$ra/cores"
chmod 0600 "$ra/autoconfig/android/H700_ANBERNIC_keys.cfg"
restorecon -R "$ra/autoconfig" "$ra/cores"
n=0
while [ ! -d /storage/emulated/0 ]; do
    n=$((n+1)); [ "$n" -lt 120 ]; sleep 1
done
cfgdir=/storage/emulated/0/Android/data/com.retroarch.ra32/files
mkdir -p "$cfgdir"
if [ ! -e "$cfgdir/retroarch.cfg" ]; then
    cp "$src/retroarch-test.cfg" "$cfgdir/retroarch.cfg"
fi
settings put global device_provisioned 1
settings --user 0 put secure user_setup_complete 1
settings --user 0 put secure enabled_accessibility_services com.roc.rgsp.navtrial/.NavigationService
settings --user 0 put secure accessibility_enabled 1
pm set-home-activity --user 0 com.overdevs.at4k/.MainActivity
echo TEST1_APPS_AND_DEFAULTS_INSTALLED >"$state/complete.tmp"
mv "$state/complete.tmp" "$state/complete"
setprop sys.h700.prototype.setup complete
am start -a android.intent.action.MAIN -c android.intent.category.HOME
