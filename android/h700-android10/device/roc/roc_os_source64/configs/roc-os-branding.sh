#!/system/bin/sh
# Defaults and legacy-name migration; retain later user-chosen names.
set -eu
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop ro.product.model)" = 'ROC OS' ]
[ "$(getprop sys.boot_completed)" = 1 ]
for namespace in global secure; do
    case "$namespace" in global) key=device_name ;; secure) key=bluetooth_name ;; esac
    current=$(settings --user 0 get "$namespace" "$key")
    case "$current" in
        ''|null|'RGSP H700'|RGSP_H700|'H700 Android USB')
            settings --user 0 put "$namespace" "$key" 'ROC OS'
            [ "$(settings --user 0 get "$namespace" "$key")" = 'ROC OS' ]
            ;;
    esac
done
