#!/system/bin/sh
# A speaker-only bind mount; underlying vendor bytes remain untouched.
set -eu
export PATH=/system/bin:/vendor/bin
mode=${1:-check}
case "$mode" in check|apply|rollback) ;; *) exit 2 ;; esac
target=/vendor/etc/audio_mixer_paths.xml
source=/data/local/tmp/rgsp-audio-trial-20260910/rgsp-speaker-probe.xml
memory=/dev/rgsp-audio-speaker-probe.xml
original=976ab6d40fe15610cf5fae3e0e3b733975c579f38a832cbb3c557cc64dbca49c
candidate=d326f8d2c06cfbf5126f50fc7a38310d06b2d0e4dfbcdbabd06b7163c83863e0
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
unmounted() {
    awk -v p="$target" '$5 == p { n++ } END { exit(n != 0) }' /proc/self/mountinfo
}
owned_mount() {
    awk -v p="$target" '$4 == "/rgsp-audio-speaker-probe.xml" && $5 == p { n++ } END { exit(n != 1) }' /proc/self/mountinfo
}
test "$(getprop ro.product.device)" = rgsp
test "$(getprop sys.boot_completed)" = 1
test "$(cat /proc/sys/kernel/random/boot_id)" = 53fae06e-3b06-4e4d-92b4-beb2febe9fd1
test "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7
test "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b
awk '$2 == "/vendor" && $1 == "/dev/mmcblk1p3" && $4 ~ /^ro,/ { n++ } END { exit(n != 1) }' /proc/mounts
test "$(stat -c '%u %g %a' /dev/snd/controlC0)" = '1000 1005 660'
test "$(stat -c '%u %g %a' /dev/snd/pcmC0D0p)" = '1000 1005 660'
test ! -L "$target"
test "$(sha "$source")" = "$candidate"

if [ "$mode" = rollback ]; then
    owned_mount
    test "$(sha "$target")" = "$candidate"
    umount "$target"
    test "$(sha "$target")" = "$original"
    # Restore the six switches observed before this trial; leave gains alone.
    for ctl in "SPK Switch" "LINEOUT Switch" "OutputL Mixer DACL Switch" \
        "OutputL Mixer DACR Switch" "OutputR Mixer DACL Switch" "OutputR Mixer DACR Switch"; do
        /data/local/tmp/rgsp-tinymix-20260910 "$ctl" 0
    done
    setprop ctl.restart audioserver
    echo RGSP_SPEAKER_ROUTE_ROLLED_BACK
    exit 0
fi

unmounted
test "$(sha "$target")" = "$original"
media volume --stream 3 --get | grep -F 'volume is 3 in range [0..15]'
echo RGSP_SPEAKER_ROUTE_PRECHECK_PASS
[ "$mode" = apply ] || exit 0
test ! -e "$memory"
cp "$source" "$memory"
chmod 0644 "$memory"
test "$(sha "$memory")" = "$candidate"
mount --bind "$memory" "$target"
if ! owned_mount || [ "$(sha "$target")" != "$candidate" ]; then
    if owned_mount; then umount "$target"; fi
    echo RGSP_SPEAKER_ROUTE_BIND_CHECK_FAILED >&2
    exit 1
fi
setprop ctl.restart audioserver
echo RGSP_SPEAKER_ROUTE_BOUND_RUNTIME_ONLY
