#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7 ]
[ "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b ]
grep -q '^/dev/mmcblk1p3 /vendor ext4 ro,' /proc/mounts

sha() { sha256sum "$1" | cut -d ' ' -f 1; }
HAL=/vendor/lib/libwifi-hal.so
RC=/vendor/etc/init/init.rgsp.rc
HAL_NEW=/data/local/tmp/fix70-libwifi-hal.so
RC_NEW=/data/local/tmp/fix70-init.rgsp.rc
HAL_SHA=9b88a56176b190a0bcada45e2571742d9f5cab8ffa66557bb0edb940c9e0a7e3
RC_SHA=72b4fc47d8e68203fa4f45578d250b91f7578c854963e2808e7217f09edf8506
[ "$(sha "$HAL_NEW")" = "$HAL_SHA" ]
[ "$(sha "$RC_NEW")" = "$RC_SHA" ]
[ "$(sha "$HAL")" = bc830db8b1344fd9846add42c8cfbd0c37a45ead4ee0dba3199c1930174f12d8 ]
[ "$(sha "$RC")" = c3310877c7fb863f1ea967f3bd9c03c0ee1b6837004360ed0544f300b193ec94 ]
B=/rgsp-persist/fix70-wifi-backup
[ ! -e "$B" ]
mkdir "$B"
cp "$HAL" "$B/libwifi-hal.so"
cp "$RC" "$B/init.rgsp.rc"
[ "$(sha "$B/libwifi-hal.so")" = "$(sha "$HAL")" ]
[ "$(sha "$B/init.rgsp.rc")" = "$(sha "$RC")" ]
svc wifi disable
sleep 3
stop vendor.wifi_hal_legacy
sleep 1
[ "$(getprop init.svc.vendor.wifi_hal_legacy)" = stopped ]

mount -o remount,rw /vendor
trap 'sync; mount -o remount,ro /vendor' EXIT
cp "$HAL_NEW" "$HAL.fix70"
cp "$RC_NEW" "$RC.fix70"
chmod 0644 "$HAL.fix70" "$RC.fix70"
chown root:root "$HAL.fix70" "$RC.fix70"
[ "$(sha "$HAL.fix70")" = "$HAL_SHA" ]
[ "$(sha "$RC.fix70")" = "$RC_SHA" ]
mv "$HAL.fix70" "$HAL"
mv "$RC.fix70" "$RC"
restorecon "$HAL" "$RC"
sync
mount -o remount,ro /vendor
trap - EXIT
[ "$(sha "$HAL")" = "$HAL_SHA" ]
[ "$(sha "$RC")" = "$RC_SHA" ]
# Emulate next boot's property initialization without claiming a loaded driver.
setprop wlan.driver.status unloaded
svc wifi enable
echo FIX70_WIFI_FILES_INSTALLED
