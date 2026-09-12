#!/system/bin/sh
# Temporary codec XML trial. Never remounts a card filesystem writable.
set -eu
mode=${1:---check}
[ "$#" -le 1 ] || exit 2
case "$mode" in --check|--probe) ;; *) exit 2 ;; esac
export PATH=/system/bin:/vendor/bin
target=/vendor/odm/etc
saved=/dev/rgsp-codec-probe-build.prop
mounted=0
saved_copy=0
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
unmounted() {
    awk -v p="$target" '$2 == p || index($2,p "/") == 1 { n++ } END { exit(n!=0) }' /proc/mounts
}
owned_mount() {
    awk -v p="$target" '$1 == "rgsp-codec-probe" && $2 == p && $3 == "tmpfs" { n++ } END { exit(n!=1) }' /proc/mounts
}
wait_running() {
    service=$1
    tries=0
    while [ "$(getprop "init.svc.$service")" != running ]; do
        tries=$((tries + 1))
        [ "$tries" -lt 20 ] || return 1
        sleep 1
    done
}
cleanup() {
    rc=$?
    trap - EXIT INT TERM
    if [ "$mounted" = 1 ] && owned_mount; then
        am force-stop org.chromium.webview_shell || true
        if ! umount "$target"; then
            echo CODEC_PROBE_CLEANUP_FAILED >&2
            exit 1
        fi
        setprop ctl.restart vendor.media.omx
        setprop ctl.restart media
        sleep 2
        if ! wait_running vendor.media.omx || ! wait_running media ||
           ! unmounted || [ "$(sha "$target/build.prop")" != "$original_prop" ] ||
           [ "$(ls -A "$target")" != build.prop ] ||
           [ "$(pidof surfaceflinger zygote system_server)" != "$core_pids" ]; then
            echo CODEC_PROBE_RESTORE_CHECK_FAILED >&2
            rc=1
        else
            echo CODEC_PROBE_RESTORED
        fi
    elif [ "$mounted" = 1 ] && ! unmounted; then
        echo CODEC_PROBE_UNKNOWN_MOUNT_PRESERVED >&2
        rc=1
    fi
    if [ "$saved_copy" = 1 ]; then rm -f "$saved"; fi
    exit "$rc"
}

[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7 ]
[ "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b ]
awk '$2 == "/vendor" && $1 == "/dev/mmcblk1p3" && $4 ~ /^ro,/ { n++ } END { exit(n!=1) }' /proc/mounts
unmounted
[ -d "$target" ] && [ ! -L "$target" ]
[ -f "$target/build.prop" ] && [ ! -L "$target/build.prop" ]
[ "$(ls -A "$target")" = build.prop ]
[ ! -e "$saved" ]
[ "$(sha /data/local/tmp/fix72-media_codecs.xml)" = 152e5797f0b9a27101faf43614b438f6b75022e9c24423e333582dccbbaed3b4 ]
[ "$(sha /data/local/tmp/fix72-media_codecs_google_audio.xml)" = f33464aee38c30e1fe52764bdb1d98ccd56a8214618d03b061b0fd63c38b0000 ]
[ "$(sha /data/local/tmp/fix72-media_codecs_google_video.xml)" = 876f5f850cbb5ce4f7a9582654ce006888903e6016dd0b8053e61ab0fd993839 ]
[ "$(getprop init.svc.vendor.media.omx)" = running ]
[ "$(getprop init.svc.media)" = running ]
core_pids=$(pidof surfaceflinger zygote system_server)
original_prop=$(sha "$target/build.prop")
echo CODEC_PROBE_CHECK_OK
[ "$mode" = --probe ] || exit 0

trap cleanup EXIT
trap 'exit 1' INT TERM
saved_copy=1
cp "$target/build.prop" "$saved"
[ "$(sha "$saved")" = "$original_prop" ]
mounted=1
mount -t tmpfs -o size=1m,mode=0755,nosuid,nodev,noexec rgsp-codec-probe "$target"
cp "$saved" "$target/build.prop"
for name in media_codecs.xml media_codecs_google_audio.xml media_codecs_google_video.xml; do
    cp "/data/local/tmp/fix72-$name" "$target/$name"
    chmod 0644 "$target/$name"
done
[ "$(sha "$target/build.prop")" = "$original_prop" ]
old_omx=$(pidof media.codec)
setprop ctl.restart vendor.media.omx
sleep 2
wait_running vendor.media.omx
[ "$(pidof media.codec)" != "$old_omx" ]
echo CODEC_PROBE_OMX_RESTARTED

am start -W -n org.chromium.webview_shell/.WebViewBrowserActivity \
    -a android.intent.action.VIEW -d https://www.baidu.com/
sleep 12
dumpsys window | grep -E 'mCurrentFocus=.*org.chromium.webview_shell'
uiautomator dump /data/local/tmp/fix72-codec-trial.xml
screencap -p /data/local/tmp/fix72-codec-trial.png
sha256sum /data/local/tmp/fix72-codec-trial.xml /data/local/tmp/fix72-codec-trial.png
echo CODEC_PROBE_CAPTURED_REVIEW_REQUIRED
