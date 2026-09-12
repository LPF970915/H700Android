#!/system/bin/sh
# One-boot probe for the two inspected card-0 nodes, not an image deployment.
set -eu
export PATH=/system/bin:/vendor/bin
test "$(getprop ro.product.device)" = rgsp
test "$(getprop sys.boot_completed)" = 1
test "$(cat /proc/sys/kernel/random/boot_id)" = 53fae06e-3b06-4e4d-92b4-beb2febe9fd1
test "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7
test "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b
test -c /dev/snd/controlC0
test -c /dev/snd/pcmC0D0p
test ! -L /dev/snd/controlC0
test ! -L /dev/snd/pcmC0D0p
test "$(stat -c '%t %T' /dev/snd/controlC0)" = '74 0'
test "$(stat -c '%t %T' /dev/snd/pcmC0D0p)" = '74 10'

rollback() {
    chown 0:0 /dev/snd/controlC0 /dev/snd/pcmC0D0p
    chmod 0600 /dev/snd/controlC0 /dev/snd/pcmC0D0p
}

case "${1:-apply}" in
    apply)
        test "$(stat -c '%u %g %a' /dev/snd/controlC0)" = '0 0 600'
        test "$(stat -c '%u %g %a' /dev/snd/pcmC0D0p)" = '0 0 600'
        media volume --stream 3 --get | grep -F 'volume is 3 in range [0..15]'
        stat -c 'BEFORE %n %u %g %a' /dev/snd/controlC0 /dev/snd/pcmC0D0p
        trap 'rollback' 0
        trap 'exit 1' HUP INT TERM
        chown 1000:1005 /dev/snd/controlC0 /dev/snd/pcmC0D0p
        chmod 0660 /dev/snd/controlC0 /dev/snd/pcmC0D0p
        test "$(stat -c '%u %g %a' /dev/snd/controlC0)" = '1000 1005 660'
        test "$(stat -c '%u %g %a' /dev/snd/pcmC0D0p)" = '1000 1005 660'
        trap - 0 HUP INT TERM
        # audioserver.rc restarts the vendor HAL as part of this operation.
        setprop ctl.restart audioserver
        ;;
    rollback)
        test "$(stat -c '%u %g %a' /dev/snd/controlC0)" = '1000 1005 660'
        test "$(stat -c '%u %g %a' /dev/snd/pcmC0D0p)" = '1000 1005 660'
        rollback
        ;;
    *) exit 2 ;;
esac
stat -c 'AFTER %n %u %g %a' /dev/snd/controlC0 /dev/snd/pcmC0D0p
echo RGSP_AUDIO_PERMISSION_OPERATION_COMPLETE
