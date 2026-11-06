#!/bin/sh
# Standard Android first-stage /dev semantics for the retained H700 shell boot.
# Only populate a new tmpfs; never relabel or reuse Linux devtmpfs char nodes.
set -eu
[ "$#" -eq 5 ] || exit 2
root=$1
sys=$2
system_dev=$3
vendor_dev=$4
data_dev=$5
case "$root" in /*) ;; *) exit 2 ;; esac
[ "$root" != / ] && [ -d "$root/dev" ] || exit 2
mountpoint -q "$root/dev" && exit 3

# Read all block identities before creating the Android device filesystem.
block_ids=
for spec in "system:$system_dev" "vendor:$vendor_dev" "userdata:$data_dev"; do
    name=${spec%%:*}
    dev=${spec#*:}
    base=${dev##*/}
    case "$base" in mmcblk[0-9]*p[0-9]*) ;; *) exit 2 ;; esac
    ids=$(cat "$sys/class/block/$base/dev")
    case "$ids" in ''|*[!0-9:]*|:*|*:) exit 2 ;; esac
    major=${ids%%:*}
    minor=${ids#*:}
    case "$minor" in *:*) exit 2 ;; esac
    block_ids="$block_ids $name:$base:$major:$minor"
done

mount -t tmpfs -o mode=0755,nosuid tmpfs "$root/dev"
mkdir -p "$root/dev/pts" "$root/dev/socket" "$root/dev/block/by-name"
chmod 0755 "$root/dev" "$root/dev/pts" "$root/dev/socket" "$root/dev/block" "$root/dev/block/by-name"
mount -t devpts devpts "$root/dev/pts"

# Match system/core/init/first_stage_init.cpp. These get tmpfs labels at
# policy load; second-stage init can open null and restore these exact nodes.
mknod -m 0600 "$root/dev/kmsg" c 1 11
mknod -m 0666 "$root/dev/random" c 1 8
mknod -m 0666 "$root/dev/urandom" c 1 9
mknod -m 0666 "$root/dev/ptmx" c 5 2
mknod -m 0666 "$root/dev/null" c 1 3

for spec in $block_ids; do
    name=${spec%%:*}; rest=${spec#*:}
    base=${rest%%:*}; rest=${rest#*:}
    major=${rest%%:*}; minor=${rest#*:}
    mknod -m 0600 "$root/dev/block/$base" b "$major" "$minor"
    ln -s "/dev/block/$base" "$root/dev/block/by-name/$name"
done
# No Binder/input/display clones and no .coldboot_done sentinel: real ueventd
# coldboot creates those with file_contexts and the retained /vendor/ueventd.rc.
[ ! -e "$root/dev/.coldboot_done" ]
echo '[roc-user-bootfix1] fresh Android tmpfs /dev ready; ueventd coldboot required'
