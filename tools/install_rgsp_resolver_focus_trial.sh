#!/system/bin/sh
# Reversible native-resource trial; final images compile the same board layouts directly.
set -eu
export PATH=/system/bin:/vendor/bin
expected=38183fce539f932296309176e6ada07ea7fa755a49f696b0c2b8a71e273fca4c
source=/data/local/tmp/rgsp-resolver-static-trial.apk
directory=/system/product/overlay/RgspResolverFocusOverlay
target=$directory/RgspResolverFocusOverlay.apk
sha() { sha256sum "$1" | cut -d ' ' -f 1; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
case "${1:-}" in
install)
    [ "$(sha "$source")" = "$expected" ]
    [ ! -e "$directory" ]
    mount -o remount,rw /
    trap 'sync; mount -o remount,ro /' EXIT
    mkdir "$directory"
    cp "$source" "$target"
    chown 0:0 "$directory" "$target"
    chmod 0755 "$directory"
    chmod 0644 "$target"
    restorecon -RF "$directory"
    [ "$(sha "$target")" = "$expected" ]
    echo RESOLVER_FOCUS_STATIC_TRIAL_INSTALLED
    ;;
remove)
    [ "$(sha "$target")" = "$expected" ]
    mount -o remount,rw /
    trap 'sync; mount -o remount,ro /' EXIT
    rm "$target"
    rmdir "$directory"
    echo RESOLVER_FOCUS_STATIC_TRIAL_REMOVED
    ;;
*) echo 'Use install or remove' >&2; exit 2 ;;
esac
