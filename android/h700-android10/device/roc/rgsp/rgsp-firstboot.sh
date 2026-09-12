#!/system/bin/sh
# Explicit local provisioning only. Never source commands from removable media.
set -eu
export PATH=/system/bin:/vendor/bin
mode=${1:-status}
case "$mode" in status|apply) ;; *) echo 'Usage: rgsp-firstboot.sh status|apply' >&2; exit 2 ;; esac
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(am get-current-user)" = 0 ]
state=/data/local/rgsp-firstboot
marker=$state/complete-v1
home() {
    cmd package resolve-activity --brief --user 0 \
        -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1
}
echo "HOME=$(home)"
echo "IME=$(settings --user 0 get secure default_input_method)"
if [ -f "$marker" ]; then
    echo 'FIRSTBOOT=complete; existing user choices preserved'
    exit 0
fi
[ "$mode" = apply ] || { echo FIRSTBOOT=not-applied; exit 0; }
[ "$(id -u)" = 0 ]
umask 077
mkdir -p "$state"
mkdir "$state/lock" || { echo FIRSTBOOT=busy >&2; exit 1; }
trap 'rmdir "$state/lock"' EXIT
leanback=com.android.inputmethod.leanback/.service.LeanbackImeService
latin=com.android.inputmethod.latin/.LatinIME
ime list -s | grep -Fxq "$leanback"
ime list -s | grep -Fxq "$latin"
pm path com.android.launcher3 | grep -q '^package:'
apk=$(pm path com.android.inputmethod.leanback | sed -n 's/^package://p' | head -n 1)
[ -f "$apk" ]
expected=$(cat /system/etc/rgsp/leanback.sha256)
[ "$(sha256sum "$apk" | cut -d ' ' -f 1)" = "$expected" ]

# A request is an explicit choice for this RGSP, not an H700-wide default.
# Installer/operator places only a known local APK at this fixed location.
at4k=/rgsp-persist/provision/AT4K-launcher.apk
at4k_sha=cd0568b8476cb8020e72c667444f8673b66e7081adbb305a3d9c8028028e7e89
installed=$(pm path com.overdevs.at4k | sed -n 's/^package://p' | head -n 1)
if [ -n "$installed" ]; then
    [ -f "$installed" ]
    [ "$(sha256sum "$installed" | cut -d ' ' -f 1)" = "$at4k_sha" ]
else
    [ -f "$at4k" ] || { echo 'AT4K_LOCAL_APK_REQUIRED; no preferences changed' >&2; exit 1; }
    [ "$(sha256sum "$at4k" | cut -d ' ' -f 1)" = "$at4k_sha" ]
    # Keep the root-owned verified copy out of shared storage during install.
    cp "$at4k" "$state/AT4K-launcher.apk"
    [ "$(sha256sum "$state/AT4K-launcher.apk" | cut -d ' ' -f 1)" = "$at4k_sha" ]
    pm install --user 0 "$state/AT4K-launcher.apk"
    rm "$state/AT4K-launcher.apk"
fi

old_ime=$(settings --user 0 get secure default_input_method)
old_home=$(home)
printf '%s\n' "$old_ime" > "$state/previous-ime"
printf '%s\n' "$old_home" > "$state/previous-home"
rollback() {
    rc=$?
    trap - EXIT
    case "$old_ime" in ''|null) old_ime=$latin ;; esac
    ime enable --user 0 "$old_ime" || true
    ime set --user 0 "$old_ime" || true
    case "$old_home" in ''|*ResolverActivity*|*' '*) old_home=com.android.launcher3/.Launcher ;; esac
    pm set-home-activity --user 0 "$old_home" || true
    rmdir "$state/lock"
    exit "$rc"
}
trap rollback EXIT
ime enable --user 0 "$leanback"
ime set --user 0 "$leanback"
[ "$(settings --user 0 get secure default_input_method)" = "$leanback" ]
sh /system/bin/set_rgsp_home.sh at4k
printf 'rgsp-fix72-v1\n' > "$state/complete-v1.tmp"
mv "$state/complete-v1.tmp" "$marker"
trap 'rmdir "$state/lock"' EXIT
echo 'FIRSTBOOT=complete'
echo 'AT4K_LAYOUT=manual: Appearance / Desktop cards / Hide desktop cards'
