#!/bin/sh
# Nonfatal pre-Android input add-on, driven only by the explicit boot model.
set -u
set -f
if [ "$#" -lt 4 ] || [ "$#" -gt 6 ]; then
    echo '[h700-input] invalid helper arguments; retaining base controller'
    exit 0
fi
root=$1
modules=$2
busybox=$3
kernel=$4
cmdline=${5:-/proc/cmdline}
sysmodules=${6:-/sys/module}
module="$root/vendor/modules/h700_stick_axes.ko"
expected_module_sha256='bc7a000ecc6ad0eaabe0cfb137ebb8b49f739b89b2473b5204ec67c437dae38f'
model=
sticks=
seen_model=0
seen_sticks=0
if [ ! -r "$cmdline" ]; then
    echo '[h700-input] boot command line unavailable; retaining base controller'
    exit 0
fi
for token in $("$busybox" cat "$cmdline"); do
    case "$token" in
        androidboot.roc_model=*)
            if [ "$seen_model" = 1 ]; then
                echo '[h700-input] duplicate boot model; retaining base controller'; exit 0
            fi
            seen_model=1; model=${token#*=} ;;
        androidboot.roc_sticks=*)
            if [ "$seen_sticks" = 1 ]; then
                echo '[h700-input] duplicate boot stick count; retaining base controller'; exit 0
            fi
            seen_sticks=1; sticks=${token#*=} ;;
    esac
done
case "$model" in
    rg34xx|rgsp|rg35xxplus|rg35xx_2025|rg28xx|rg35xxsp) expected_sticks=0 ;;
    rg40xxv) expected_sticks=1 ;;
    rg34xxsp|rgcubexx|rg35xxh|rg40xxh|rg35xxpro) expected_sticks=2 ;;
    *) echo '[h700-input] explicit canonical boot model unavailable; retaining base controller'; exit 0 ;;
esac
if [ "$seen_sticks" != 1 ] || [ "$sticks" != "$expected_sticks" ]; then
    echo "[h700-input] model=$model stick metadata mismatch; retaining base controller"
    exit 0
fi
if [ "$sticks" = 0 ]; then
    echo "[h700-input] model=$model sticks=0; no ADC/GPIO add-on requested"
    exit 0
fi
if [ "$kernel" != 4.9.170 ] || [ ! -r "$module" ]; then
    echo "[h700-input] model=$model module/kernel unavailable; retaining base controller"
    exit 0
fi
actual_sha=$("$busybox" sha256sum "$module") || exit 0
actual_sha=${actual_sha%% *}
if [ "$actual_sha" != "$expected_module_sha256" ]; then
    echo "[h700-input] model=$model module hash mismatch; retaining base controller"
    exit 0
fi
if "$busybox" grep -q '^h700_stick_axes ' "$modules"; then
    loaded_profile=$("$busybox" cat "$sysmodules/h700_stick_axes/parameters/profile" 2>/dev/null) || loaded_profile=
    if [ "$loaded_profile" = "$model" ]; then
        echo "[h700-input] model=$model sticks=$sticks matching add-on already loaded"
    else
        echo "[h700-input] model=$model loaded profile=$loaded_profile differs; refusing duplicate load"
    fi
    exit 0
fi
if "$busybox" insmod "$module" "profile=$model"; then
    echo "[h700-input] model=$model sticks=$sticks add-on active"
else
    echo "[h700-input] model=$model add-on refused by hardware/ABI guards; retaining base controller"
fi
exit 0
