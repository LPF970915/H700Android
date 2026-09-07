#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin
mode=${1:-status}
case "$mode" in leanback|latin|status) ;; *) exit 2 ;; esac
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
previous=$(settings get secure default_input_method)
echo "IME_BEFORE=$previous"
[ "$mode" != status ] || exit 0

latin=com.android.inputmethod.latin/.LatinIME
target=$latin
ime list -s | grep -Fxq "$latin"
if [ "$mode" = leanback ]; then
    target=com.android.inputmethod.leanback/.service.LeanbackImeService
    apk=$(pm path com.android.inputmethod.leanback | sed -n 's/^package://p' | head -n 1)
    [ -n "$apk" ] && [ -f "$apk" ]
    [ "$(sha256sum "$apk" | cut -d ' ' -f 1)" = 2a57b52cbac36d09138f7d94ba43f5d7fa9c4175966f7f1b43bb004b1a83ff18 ]
fi
record=$(mktemp -d /data/local/tmp/rgsp-ime.XXXXXX)
printf '%s\n' "$previous" > "$record/previous.txt"
echo "IME_RECORD=$record"
rollback=$latin
case "$previous" in "$latin"|com.android.inputmethod.leanback/*) rollback=$previous ;; esac
restore() {
    rc=$?
    trap - EXIT
    ime enable "$rollback" || true
    ime set "$rollback" || true
    exit "$rc"
}
trap restore EXIT
ime enable "$target"
ime set "$target"
[ "$(settings get secure default_input_method)" = "$target" ]
trap - EXIT
echo "IME_SWITCH_OK=$target"
