#!/bin/sh
# Optional board-specific extension: never make Android depend on this driver.
# The module retains its own GPIO/ADC/ownership checks; refusal is not boot failure.
set -u
if [ "$#" -ne 4 ]; then
    echo '[h700-input] optional axes arguments unavailable; base controller retained'
    exit 0
fi
root=$1
modules=$2
busybox=$3
kernel=$4
module="$root/vendor/modules/h700_stick_axes.ko"
if [ "$kernel" != 4.9.170 ]; then
    echo '[h700-input] optional axes kernel ABI not matched; base controller retained'
    exit 0
fi
if [ ! -r "$module" ]; then
    echo '[h700-input] optional axes payload absent; base controller retained'
    exit 0
fi
digest=$("$busybox" sha256sum "$module" 2>/dev/null)
digest=${digest%% *}
if [ "$digest" != 9c8eacf887cd9d00f5416c05b24118ce625e4deef73003f79ea1805c6a31faf5 ]; then
    echo '[h700-input] optional axes identity not matched; base controller retained'
    exit 0
fi
if grep -q '^h700_stick_axes ' "$modules" 2>/dev/null; then
    echo '[h700-input] optional axes already loaded'
    exit 0
fi
if "$busybox" insmod "$module" profile=rg34xxsp; then
    echo '[h700-input] optional RG34XXSP axes active'
else
    echo '[h700-input] optional axes not applicable or refused; base controller retained; continuing Android'
fi
exit 0
