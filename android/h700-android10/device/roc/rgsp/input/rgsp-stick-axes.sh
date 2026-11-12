#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin

# Product labels cannot distinguish older RGSP units. Enabling this driver is
# an explicit per-device choice, never inferred from the shared product name.
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ] || exit 0
[ "$(getprop ro.product.device)" = rgsp ] || exit 1
[ "$(uname -r)" = 4.9.170 ] || exit 1
if grep -q '^h700_stick_axes ' /proc/modules; then exit 0; fi
if insmod /vendor/modules/h700_stick_axes.ko profile=rg34xxsp; then
    log -t RGSPSticks 'RG34XXSP axes added to original controller'
else
    log -p e -t RGSPSticks 'Stick add-on refused; original controller retained'
    exit 1
fi
