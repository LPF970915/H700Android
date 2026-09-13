#!/system/bin/sh
# Run through Android's live package manager; never edit packages.xml offline.
set -eu
export PATH=/system/bin:/vendor/bin

mode=${1:-status}
case "$mode" in at4k|rgsp|launcher3|status) ;; *) echo 'Usage: set_rgsp_home.sh at4k|rgsp|launcher3|status' >&2; exit 2 ;; esac
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]

home() {
    cmd package resolve-activity --brief --user 0 \
        -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1
}
previous=$(home)
printf 'HOME_BEFORE=%s\n' "$previous"
[ "$mode" != status ] || exit 0

fallback=com.android.launcher3/.Launcher
pm path com.android.launcher3 | grep -q '^package:'
target=$fallback
if [ "$mode" = at4k ]; then
    target=com.overdevs.at4k/.MainActivity
    apk=$(pm path com.overdevs.at4k | sed -n 's/^package://p' | head -n 1)
    [ -n "$apk" ] && [ -f "$apk" ] || {
        echo 'AT4K_NOT_INSTALLED: install the verified user APK as an ordinary app first.' >&2
        exit 1
    }
    expected=b6b2a3db335e5f2a27c284fc48ece6de9ccaf46a8886222aef07c17a26ee5d5b
    input_sha=700276cb79c1e11e974c3fc10ab2edebbb2d381e5af8c60a241b52d3f6e039af
    actual_sha=$(sha256sum "$apk" | cut -d ' ' -f 1)
    [ "$actual_sha" = "$expected" ] || [ "$actual_sha" = "$input_sha" ] || {
        echo 'AT4K_APK_HASH_MISMATCH: stop for review.' >&2
        exit 1
    }
elif [ "$mode" = rgsp ]; then
    target=com.roc.rgsp.launcher/.MainActivity
    apk=$(pm path com.roc.rgsp.launcher | sed -n 's/^package://p' | head -n 1)
    [ -n "$apk" ] && [ -f "$apk" ] || {
        echo 'RGSP_LAUNCHER_NOT_INSTALLED: build and install RGSPLauncher first.' >&2
        exit 1
    }
fi

# Retain a local record; no system-image remount, APK privileges or accessibility.
record=$(mktemp -d /data/local/tmp/rgsp-home.XXXXXX)
printf '%s\n' "$previous" > "$record/previous-home.txt"
printf '%s\n' "$target" > "$record/requested-home.txt"
printf 'HOME_RECORD=%s\n' "$record"

# First check launchability before changing the HOME role.
timeout 15 am start -W --user 0 -n "$target" > "$record/launch.txt" 2>&1
cat "$record/launch.txt"
grep -q '^Status: ok' "$record/launch.txt" || {
    echo 'HOME_LAUNCH_FAILED: default unchanged.' >&2
    exit 1
}

rollback=$fallback
case "$previous" in
    com.android.launcher3/*|com.overdevs.at4k/*|com.roc.rgsp.launcher/*) rollback=$previous ;;
esac
restore() {
    rc=$?
    trap - EXIT
    echo "HOME_SWITCH_FAILED: restoring $rollback" >&2
    pm set-home-activity --user 0 "$rollback" || true
    am start --user 0 -n "$rollback" || true
    exit "$rc"
}
trap restore EXIT
pm set-home-activity --user 0 "$target"
actual=$(home)
printf 'HOME_AFTER=%s\n' "$actual"
printf '%s\n' "$actual" > "$record/resolved-home.txt"
[ "${actual%%/*}" = "${target%%/*}" ]
timeout 15 am start -W --user 0 -a android.intent.action.MAIN \
    -c android.intent.category.HOME > "$record/home-intent.txt" 2>&1
cat "$record/home-intent.txt"
grep -q '^Status: ok' "$record/home-intent.txt"
trap - EXIT
echo HOME_SWITCH_OK
echo 'Check physical Menu/HOME, A, B and Settings on the device.'
