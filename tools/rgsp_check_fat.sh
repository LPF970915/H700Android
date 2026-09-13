#!/bin/sh
# Recover only checked dirty status / stale FSInfo counts, never file chains.
set -eu
export LC_ALL=C LANG=C
export GCONV_PATH=/grow/lib/gconv
fsck_readonly() {
    /grow/lib/ld-linux-aarch64.so.1 --library-path /grow/lib \
        /grow/fsck.fat -n "$roms"
}
roms=${1:?ROMS device required}
state=${2:?Mounted data journal required}
[ "$roms" = /dev/mmcblk0p8 ] && [ -b "$roms" ]
awk -v p="$roms" '$1==p || $1=="/dev/block/mmcblk0p8" {bad=1} END {exit bad}' /proc/mounts
work=$(mktemp -d /tmp/rgsp-fat-check.XXXXXX)
trap 'rm -f "$work/report" "$work/before" "$work/candidate" "$work/backup" "$work/recheck" "$work/info" "$work/info-new" "$work/count"; rmdir "$work"' EXIT
stop() { echo "[rgsp-fat-check] ERROR: $*; volume not auto-formatted" >&2; exit 1; }
rc=0
fsck_readonly > "$work/report" 2>&1 || rc=$?
cat "$work/report"
[ "$rc" != 0 ] || exit 0
[ "$rc" = 1 ] || stop 'read-only check failed'

# dosfstools has no structured diagnostic API. Fail closed on any other text,
# including FAT/directory errors, I/O errors or an unqualified tool version.
dirty=0
difference=0
summary=0
count_errors=0
count_fix=0
old_free=
new_free=
used=
total=
while IFS= read -r line; do
    case "$line" in
        'Dirty bit is set. Fs was not properly unmounted and some data may be corrupt.')
            dirty=$((dirty + 1)) ;;
        '  65:01/00') difference=$((difference + 1)) ;;
        "$roms":\ [0-9]*\ files,\ [0-9]*/[0-9]*\ clusters)
            summary=$((summary + 1))
            counts=$(printf '%s\n' "$line" | sed -n 's/^.*: [0-9][0-9]* files, \([0-9][0-9]*\)\/\([0-9][0-9]*\) clusters$/\1 \2/p')
            [ -n "$counts" ] || stop 'invalid cluster summary'
            used=${counts% *}
            total=${counts#* } ;;
        'Free cluster summary wrong ('*')')
            counts=$(printf '%s\n' "$line" | sed -n 's/^Free cluster summary wrong (\([0-9][0-9]*\) vs\. really \([0-9][0-9]*\))$/\1 \2/p')
            [ -n "$counts" ] || stop 'invalid free cluster diagnostic'
            old_free=${counts% *}
            new_free=${counts#* }
            count_errors=$((count_errors + 1)) ;;
        '  Auto-correcting.') count_fix=$((count_fix + 1)) ;;
        ''|'fsck.fat 4.2 (2021-01-31)'|\
        'There are differences between boot sector and its backup.'|\
        'This is mostly harmless. Differences: (offset:original/backup)'|\
        '  Not automatically fixing this.'|\
        ' Automatically removing dirty bit.'|\
        'Leaving filesystem unchanged.') ;;
        *) stop 'additional or unrecognized filesystem diagnostic' ;;
    esac
done < "$work/report"
[ "$dirty" -le 1 ] && [ "$difference" = "$dirty" ] &&
    [ "$summary" = 1 ] && [ "$count_errors" -le 1 ] &&
    [ "$count_fix" = "$count_errors" ] &&
    [ "$((dirty + count_errors))" -gt 0 ] ||
    stop 'not a qualified metadata-only case'

dd if="$roms" of="$work/before" bs=512 count=1 2>/dev/null
[ "$(wc -c < "$work/before" | tr -d ' \n')" = 512 ]
byte() { /bin/busybox od -An -tu1 -j "$1" -N1 "$work/before" | tr -d ' \n'; }
[ "$(byte 11)" = 0 ] && [ "$(byte 12)" = 2 ] &&
    [ "$(byte 16)" = 2 ] && [ "$(byte 17)" = 0 ] && [ "$(byte 18)" = 0 ] &&
    [ "$(byte 22)" = 0 ] && [ "$(byte 23)" = 0 ] &&
    [ "$(byte 50)" = 6 ] && [ "$(byte 51)" = 0 ] &&
    [ "$(byte 65)" = "$dirty" ] || stop 'unexpected FAT32 boot metadata'
[ "$(dd if="$work/before" bs=1 skip=82 count=8 2>/dev/null)" = 'FAT32   ' ] ||
    stop 'unexpected FAT32 type label'
dd if="$roms" of="$work/backup" bs=512 skip=6 count=1 2>/dev/null
cp "$work/before" "$work/candidate"
dd if=/dev/zero of="$work/candidate" bs=1 seek=65 count=1 conv=notrunc 2>/dev/null
cmp -s "$work/candidate" "$work/backup" ||
    stop 'boot sectors differ by more than the dirty flag'

# FSInfo is only a cache. Accept the count derived by the full FAT scan,
# cross-check against its cluster summary, and change no allocation entries.
if [ "$count_errors" = 1 ]; then
    [ "$(byte 48)" = 1 ] && [ "$(byte 49)" = 0 ] ||
        stop 'unexpected FSInfo location'
    dd if="$roms" of="$work/info" bs=512 skip=1 count=1 2>/dev/null
    [ "$(wc -c < "$work/info" | tr -d ' \n')" = 512 ]
    word() { /bin/busybox od -An -tu4 -j "$1" -N4 "$work/info" | tr -d ' \n'; }
    [ "$(word 0)" = 1096897106 ] && [ "$(word 484)" = 1631679090 ] &&
        [ "$(word 508)" = 2857697280 ] && [ "$(word 488)" = "$old_free" ] ||
        stop 'invalid FSInfo signatures or changed cached count'
    [ "$total" -gt 0 ] && [ "$total" -lt 268435445 ] &&
        [ "$used" -le "$total" ] &&
        [ "$new_free" = "$((total - used))" ] ||
        stop 'free count does not match scanned allocation summary'
    cp "$work/info" "$work/info-new"
    # printf emits little-endian bytes without shell variables holding NULs.
    for shift in 0 8 16 24; do
        octal=$(printf '%03o' "$(((new_free >> shift) & 255))")
        printf "\\$octal"
    done > "$work/count"
    [ "$(wc -c < "$work/count" | tr -d ' \n')" = 4 ]
    dd if="$work/count" of="$work/info-new" bs=1 seek=488 count=4 conv=notrunc 2>/dev/null
fi

bootid=$(cat /proc/sys/kernel/random/boot_id)
case "$bootid" in ''|*[!0-9a-f-]*) stop 'invalid boot ID' ;; esac
backup=$state/rgsp-fat-dirty-$bootid
umask 077
mkdir "$backup"
cp "$work/before" "$backup/boot-sector.before"
cp "$work/report" "$backup/fsck.before"
cp "$work/candidate" "$backup/boot-sector.expected"
if [ "$count_errors" = 1 ]; then
    cp "$work/info" "$backup/fsinfo.before"
    cp "$work/info-new" "$backup/fsinfo.expected"
fi
sync
dd if="$roms" of="$work/recheck" bs=512 count=1 2>/dev/null
cmp -s "$work/before" "$work/recheck" || stop 'boot sector changed during check'
if [ "$count_errors" = 1 ]; then
    dd if="$roms" of="$work/recheck" bs=512 skip=1 count=1 2>/dev/null
    cmp -s "$work/info" "$work/recheck" || stop 'FSInfo changed during check'
    dd if="$work/count" of="$roms" bs=1 seek=1000 count=4 conv=notrunc 2>/dev/null
    sync
    dd if="$roms" of="$work/recheck" bs=512 skip=1 count=1 2>/dev/null
    cmp -s "$work/info-new" "$work/recheck" || stop 'FSInfo readback failed'
fi
if [ "$dirty" = 1 ]; then
    dd if=/dev/zero of="$roms" bs=1 seek=65 count=1 conv=notrunc 2>/dev/null
fi
sync
dd if="$roms" of="$work/recheck" bs=512 count=1 2>/dev/null
cmp -s "$work/candidate" "$work/recheck" || stop 'dirty flag readback failed'
fsck_readonly > "$backup/fsck.after" 2>&1 ||
    stop 'post-repair consistency check failed'
printf 'dirty_repaired=%s fsinfo_repaired=%s free_before=%s free_after=%s\n' \
    "$dirty" "$count_errors" "$old_free" "$new_free" > "$backup/complete"
sync
echo '[rgsp-fat-check] METADATA_ONLY_REPAIRED_AND_VERIFIED'
