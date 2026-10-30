#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin
base=/data/local/tmp/h700-dualabi-prototype-20261030
r=$base/rootfs
[ "$(readlink /proc/self/ns/mnt)" != "$1" ]
mkdir -p "$r/proc" "$r/sys" "$r/dev/__properties__"
"$base/mount64" "$1"
echo MOUNT_NAMESPACE_PRIVATE
for name in proc sys dev/__properties__; do
 "$base/mount64" "$1" "/$name" "$r/$name"
 "$base/mount64" "$1" "$r/$name"
done
for name in null zero urandom random ashmem binder hwbinder vndbinder mali0 ion; do
 [ ! -e "/dev/$name" ] || "$base/mount64" "$1" "/dev/$name" "$r/dev/$name"
done
shift
# Fixed executable and bounded window lifetime; outer controller also sets a timeout.
exec chroot "$r" /system/bin/linker64 /system/bin/h700_window_probe64 30
