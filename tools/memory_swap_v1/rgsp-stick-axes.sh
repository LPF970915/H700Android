#!/system/bin/sh
# Android's legacy service follows the same selected model and exact module.
# persist.vendor.rgsp.input_profile also controls media and is not model identity.
set -u
set -f
model=$(getprop ro.boot.roc_model)
sticks=$(getprop ro.boot.roc_sticks)
case "$model" in
    rg34xx|rgsp|rg35xxplus|rg35xx_2025|rg28xx|rg35xxsp) expected_sticks=0 ;;
    rg40xxv) expected_sticks=1 ;;
    rg34xxsp|rgcubexx|rg35xxh|rg40xxh|rg35xxpro) expected_sticks=2 ;;
    *) log -t RGSPSticks 'Canonical boot model unavailable; base controller retained'; exit 0 ;;
esac
if [ "$sticks" != "$expected_sticks" ]; then
    log -p e -t RGSPSticks "model=$model stick metadata mismatch; base controller retained"
    exit 0
fi
if [ "$sticks" = 0 ]; then
    log -t RGSPSticks "model=$model has no sticks; no ADC/GPIO add-on requested"
    exit 0
fi
if [ "$(uname -r)" != 4.9.170 ]; then
    log -p e -t RGSPSticks "model=$model kernel mismatch; base controller retained"
    exit 0
fi
module=/vendor/modules/h700_stick_axes.ko
expected_module_sha256='5a017572b601ac8ae70216852cce3763428d5fa5793c4767812c8caf7b2d0deb'
actual_sha=$(sha256sum "$module") || exit 0
actual_sha=${actual_sha%% *}
if [ "$actual_sha" != "$expected_module_sha256" ]; then
    log -p e -t RGSPSticks "model=$model module hash mismatch; base controller retained"
    exit 0
fi
if grep -q '^h700_stick_axes ' /proc/modules; then
    loaded_profile=$(cat /sys/module/h700_stick_axes/parameters/profile 2>/dev/null) || loaded_profile=
    if [ "$loaded_profile" = "$model" ]; then
        log -t RGSPSticks "model=$model matching add-on already active"
    else
        log -p e -t RGSPSticks "model=$model loaded profile=$loaded_profile differs; refusing duplicate load"
    fi
    exit 0
fi
if insmod "$module" "profile=$model"; then
    log -t RGSPSticks "model=$model sticks=$sticks add-on active"
else
    log -p e -t RGSPSticks "model=$model add-on refused by hardware/ABI guards; base controller retained"
fi
exit 0
