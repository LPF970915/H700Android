#!/system/bin/sh
# Keep HTTP/HTTPS validation enabled. Preserve any configured endpoint choices.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
set_default() {
    current=$(settings get global "$1")
    case "$current" in
        null|'') settings put global "$1" "$2" ;;
    esac
}
set_default captive_portal_https_url https://connectivitycheck.platform.hicloud.com/generate_204
set_default captive_portal_http_url http://connect.rom.miui.com/generate_204
set_default captive_portal_fallback_url http://connectivitycheck.platform.hicloud.com/generate_204
set_default captive_portal_other_fallback_urls http://connect.rom.miui.com/generate_204
echo H700_NETWORK_VALIDATION_DEFAULTS_READY
