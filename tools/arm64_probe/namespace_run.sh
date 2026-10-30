#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin
r=/data/local/tmp/h700-arm64-isolated-20261030/rootfs
[ "$(readlink /proc/self/ns/mnt)" != "$1" ]
mkdir -p "$r/proc" "$r/sys" "$r/dev/__properties__"
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1"
echo MOUNT_NAMESPACE_PRIVATE
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" /proc "$r/proc"
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" "$r/proc"
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" /sys "$r/sys"
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" "$r/sys"
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" /dev/__properties__ "$r/dev/__properties__"
/data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" "$r/dev/__properties__"
for name in null zero urandom random ashmem binder hwbinder vndbinder mali0 ion; do
 [ ! -e "/dev/$name" ] || /data/local/tmp/h700-arm64-isolated-20261030/mount64 "$1" "/dev/$name" "$r/dev/$name"
done
chmod 0755 "$r/system/bin/linker64" "$r/system/bin/probe" "$r/data/local/tmp/h700-arm64-isolated-20261030/linker64"
shift
binary=${PROBE_BINARY:-/system/bin/probe}
case "$binary" in /system/bin/probe|/system/bin/probe-linked) ;; *) exit 9 ;; esac
exec chroot "$r" /system/bin/linker64 "$binary" "$@"
