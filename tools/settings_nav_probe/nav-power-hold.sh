#!/system/bin/sh
# Real evdev hold/release: let PhoneWindowManager's policy timer handle long press.
set -eu
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(cat /sys/class/input/event0/device/name)" = axp2202-pek ]
release() { sendevent /dev/input/event0 1 116 0; sendevent /dev/input/event0 0 0 0; }
trap release EXIT
sendevent /dev/input/event0 1 116 1
sendevent /dev/input/event0 0 0 0
sleep 1
