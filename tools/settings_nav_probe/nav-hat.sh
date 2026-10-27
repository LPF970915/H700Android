#!/system/bin/sh
# Inject the same evdev scan codes and HAT axes as this verified RGSP controller.
[ "$(cat /sys/class/input/event1/device/name)" = ANBERNIC-keys ] || exit 2
e=/dev/input/event1
duration=0.12
case "${2:-0.12}" in 0.12) ;; 0.8) duration=0.8;; *) exit 2;; esac
case "$1:$duration" in b:0.8|home:0.8|select:0.8) exit 2;; esac
case "$1" in
    up) type=3; code=17; value=-1;;
    down) type=3; code=17; value=1;;
    left) type=3; code=16; value=-1;;
    right) type=3; code=16; value=1;;
    a) type=1; code=304; value=1;;
    b) type=1; code=305; value=1;;
    home) type=1; code=312; value=1;;
    select) type=1; code=310; value=1;;
    *) exit 2;;
esac
release() { sendevent "$e" "$type" "$code" 0; sendevent "$e" 0 0 0; }
trap release EXIT
sendevent "$e" "$type" "$code" "$value" || exit 3
sendevent "$e" 0 0 0 || exit 3
sleep "$duration"
