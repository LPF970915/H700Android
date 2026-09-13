#!/system/bin/sh
# Publish bundled originals for the image picker; never replace a user's file.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(am get-current-user)" = 0 ]
source=/system/media/wallpapers
destination=/storage/emulated/0/Pictures/Wallpapers
[ -d /storage/emulated/0 ] || exit 0
mkdir -p "$destination"
for image in "$source"/*.jpg; do
    [ -f "$image" ] || continue
    target="$destination/${image##*/}"
    [ ! -e "$target" ] && [ ! -L "$target" ] || continue
    temp=$(mktemp "$destination/.wallpaper.XXXXXX")
    trap 'rm -f "$temp"' EXIT
    cp "$image" "$temp"
    [ "$(sha256sum "$image" | cut -d ' ' -f 1)" = \
      "$(sha256sum "$temp" | cut -d ' ' -f 1)" ]
    mv -n "$temp" "$target"
    rm -f "$temp"
    trap - EXIT
    am broadcast --user 0 -a android.intent.action.MEDIA_SCANNER_SCAN_FILE \
        -d "file://$target"
done
