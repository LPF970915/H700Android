#!/system/bin/sh
# Fixed, image-owned inputs only. Never execute or install removable content.
set -eu
export PATH=/system/bin:/vendor/bin
[ "${1:-status}" = apply ] || { echo 'Use apply on the labelled fresh image'; exit 0; }
[ "$(id -u)" = 0 ]
[ "$(getprop ro.h700.release)" = v6a-rg34xxsp-20261030 ]
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(am get-current-user)" = 0 ]
src=/system/etc/h700-preinstall
state=/data/local/h700-preinstall-v6a
umask 022
mkdir -p "$state"
[ ! -f "$state/complete" ] || exit 0
mkdir "$state/lock" || exit 1
trap 'rmdir "$state/lock"' EXIT
setprop sys.h700.preinstall working
cd "$src"
sha256sum -c SHA256SUMS > "$state/verify.log"
while read -r pkg apk digest; do
    [ -n "$pkg" ] || continue
    installed=$(pm path "$pkg" | sed -n 's/^package://p' | head -n 1)
    if [ -z "$installed" ]; then
        pm install -g --user 0 "$src/apks/$apk" >> "$state/install.log"
        installed=$(pm path "$pkg" | sed -n 's/^package://p' | head -n 1)
    fi
    [ -f "$installed" ]
    [ "$(sha256sum "$installed" | cut -d ' ' -f 1)" = "$digest" ]
done < "$src/apps.list"

# Wait for emulated storage and the existing partition-8 handoff. No formatting.
n=0
while :; do
    volume=$(sm list-volumes public | awk '$2 == "mounted" && $1 == "public:179,8" {print $3}')
    case "$volume" in ''|*[!A-Za-z0-9-]*) volume= ;; esac
    [ -d /storage/emulated/0 ] && [ -n "$volume" ] && break
    n=$((n + 1)); [ "$n" -lt 120 ]; sleep 1
done
romroot=/storage/$volume/PegasusGBA/Roms
mkdir -p "$romroot/GBA" "$romroot/GBA hack" "$romroot/GBA vib"
touch "/storage/$volume/PegasusGBA/.nomedia"

seed_files() {
    archive=$1
    destination=$2
    temp=$state/unpack-$archive
    mkdir -p "$temp"
    tar -xf "$src/$archive" -C "$temp"
    cp -Rn "$temp/." "$destination/"
    # This fixed state-owned directory contains only verified archive members.
    case "$temp" in /data/local/h700-preinstall-v6a/unpack-*.tar) rm -rf "$temp" ;; *) exit 1 ;; esac
}

# Retry-safe config seed: never overwrite files the user has already changed.
if [ ! -f "$state/external" ]; then
    seed_files external.tar /storage/emulated/0
    pg=/storage/emulated/0/Android/data/org.pegasus_frontend.android/files/pegasus-frontend
    for col in GBA 'GBA hack' 'GBA vib'; do
        dest="$pg/collections/$col/metadata.pegasus.txt"
        if [ ! -f "$dest" ]; then
            mkdir -p "${dest%/*}"
            sed "s|@H700_ROMS_ROOT@|$romroot|g" "$src/collections/$col/metadata.pegasus.txt" > "$dest.tmp"
            mv "$dest.tmp" "$dest"
        fi
    done
    touch "$state/external"
fi

seed_private() {
    pkg=$1
    archive=$2
    marker=$state/$pkg
    [ ! -f "$marker" ] || return 0
    dest=/data/user/0/$pkg
    [ -d "$dest" ] && [ ! -L "$dest" ]
    owner=$(stat -c %u "$dest")
    [ "$owner" -ge 10000 ]
    seed_files "$archive" "$dest"
    chown -R "$owner:$owner" "$dest"
    restorecon -RF "$dest"
    touch "$marker"
}
seed_private com.retroarch.ra32 retroarch-private.tar
chmod 0700 /data/user/0/com.retroarch.ra32/cores/*_libretro_android.so
seed_private org.courville.nova nova-private.tar
# Installing another HOME-capable frontend can clear Android's preferred HOME.
# Reassert the requested factory launcher once; the completion marker preserves
# every later user choice.
pm set-home-activity --user 0 com.overdevs.at4k/.MainActivity
resolved=$(cmd package resolve-activity --brief --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1)
[ "$resolved" = com.overdevs.at4k/.MainActivity ]
printf 'v6a-rg34xxsp-20261030\n' > "$state/complete.tmp"
mv "$state/complete.tmp" "$state/complete"
setprop sys.h700.preinstall complete
log -t H700Preinstall 'Seven selected applications and ROM-free defaults ready'
