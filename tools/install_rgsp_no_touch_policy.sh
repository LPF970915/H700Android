#!/system/bin/sh
# Install only the reviewed no-touch feature override; reboot is a separate step.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(getprop ro.product.device)" = rgsp ]
src=/data/local/tmp/rgsp-no-touch-policy-20261027/policy.xml
dst=/vendor/etc/permissions/android.hardware.touchscreen.unavailable.xml
tmp=/vendor/etc/permissions/android.hardware.touchscreen.unavailable.xml.new
expected=35a31dc53804a48aaf354890edf4fc7792bba8093deb9291e48ba4d939f095c2
[ "$(sha256sum "$src" | cut -d ' ' -f 1)" = "$expected" ]
grep -q '^/dev/mmcblk0p6 /vendor ext4 ro,' /proc/mounts
if [ -e "$dst" ]; then
    [ "$(sha256sum "$dst" | cut -d ' ' -f 1)" = "$expected" ]
    echo NO_TOUCH_POLICY_ALREADY_INSTALLED_REBOOT_REQUIRED
    exit 0
fi
[ ! -e "$tmp" ]
ok=0
published=0
cleanup() {
    result=$?
    if [ "$ok" != 1 ]; then
        rm -f "$tmp"
        if [ "$published" = 1 ] && [ "$(sha256sum "$dst" | cut -d ' ' -f 1)" = "$expected" ]; then
            rm "$dst"
        fi
    fi
    mount -o remount,ro /vendor
    exit "$result"
}
mount -o remount,rw /vendor
trap cleanup EXIT
cp "$src" "$tmp"
chmod 0644 "$tmp"
chown 0:0 "$tmp"
[ "$(sha256sum "$tmp" | cut -d ' ' -f 1)" = "$expected" ]
mv "$tmp" "$dst"
published=1
restorecon "$dst"
[ "$(sha256sum "$dst" | cut -d ' ' -f 1)" = "$expected" ]
mount -o remount,ro /vendor
grep -q '^/dev/mmcblk0p6 /vendor ext4 ro,' /proc/mounts
ok=1
echo NO_TOUCH_POLICY_INSTALLED_REBOOT_REQUIRED
