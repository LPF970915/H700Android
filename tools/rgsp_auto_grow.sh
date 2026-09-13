#!/bin/sh
# Called from the single-card ramdisk, before any ROMS mount.
set -eu
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
disk=/dev/mmcblk0
roms=${disk}p8
data=${disk}p7
state=/grow-state
pending=$state/.rgsp-fat-grow-pending-v1
say() { echo "[rgsp-grow] $*"; }
stop() { say "ERROR: $*; no automatic formatting"; exit 1; }
fat() {
    /grow/lib/ld-linux-aarch64.so.1 --library-path /grow/lib \
        /grow/rgsp-grow-fat "$roms" "$@"
}
awk -v d="$disk" -v p="$roms" '$1==d || $1==p {bad=1} END {exit bad}' /proc/mounts ||
    stop 'boot disk or ROMS already mounted'
[ -b "$disk" ] && [ -b "$roms" ] && [ -b "$data" ] || stop 'missing boot partitions'
/grow/rgsp-grow-gpt --check "$disk" || stop 'GPT check failed'
mkdir -p "$state"
mount -t ext4 -o rw,noatime "$data" "$state" || stop 'Android data is not a mountable ext4 volume'
trap 'umount "$state" || true' EXIT
[ ! -f "$pending" ] || stop 'previous filesystem resize was interrupted; offline recovery required'
/sbin/fsck.fat -n "$roms" || stop 'FAT32 consistency check failed before resize'
rc=0
/grow/rgsp-grow-gpt --apply "$disk" || rc=$?
if [ "$rc" = 3 ]; then
    say 'GPT committed; kernel requires restart to refresh p8'
    umount "$state"
    trap - EXIT
    sync
    /sbin/reboot -f
    exit 1
fi
[ "$rc" = 0 ] || stop 'GPT expansion failed'
rc=0
fat --check || rc=$?
if [ "$rc" = 4 ]; then
    say 'expanding FAT32 while preserving files'
    printf 'RGSP FAT32 resize in progress\n' > "$pending"
    sync
    fat || stop 'filesystem resize failed; journal retained'
    # libparted preserves files but does not carry the boot-sector volume label.
    /grow/lib/ld-linux-aarch64.so.1 --library-path /grow/lib \
        /grow/fatlabel "$roms" ROMS || stop 'unable to restore ROMS volume label'
    /sbin/fsck.fat -n "$roms" || stop 'filesystem verification failed; journal retained'
    fat --check || stop 'filesystem does not use the expanded partition'
    rm "$pending"
    printf 'capacity_sectors=%s\n' "$(cat /sys/class/block/mmcblk0/size)" > "$state/.rgsp-capacity-v1"
    sync
elif [ "$rc" != 0 ]; then
    stop 'unable to determine FAT32 capacity'
fi
say 'partition and filesystem capacity verified'
umount "$state"
trap - EXIT
