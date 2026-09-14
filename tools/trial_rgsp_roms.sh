#!/system/bin/sh
# Per-file overlays for the qualified ROMS-vold build; no firmware replacement.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-roms-v1
expected=${1:?Expected compiled vold SHA256 required}
[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(cat /sys/class/block/mmcblk0p8/start)" = 54960128 ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
[ "$(sha256sum "$stage/vold" | cut -d ' ' -f 1)" = "$expected" ]
[ ! -e "$stage/trial-active" ]
for target in /system/bin/vold /vendor/etc/fstab.sun50iw9p1 /vendor/bin/rgsp-kmsg-start.sh; do
    awk -v p="$target" '$5==p {bad=1} END {exit bad}' /proc/self/mountinfo
done
chmod 0755 "$stage/vold" "$stage/rgsp-kmsg-start.sh" "$stage/rgsp-roms-handoff.sh"
chmod 0644 "$stage/fstab.sun50iw9p1"
chcon u:object_r:vold_exec:s0 "$stage/vold"
chcon u:object_r:vendor_file:s0 "$stage/rgsp-kmsg-start.sh"
chcon u:object_r:vendor_configs_file:s0 "$stage/fstab.sun50iw9p1"
stop vold
stop rgsp-kmsg-bounded
tries=0
while [ "$(getprop init.svc.vold)" != stopped ] ||
      [ "$(getprop init.svc.rgsp-kmsg-bounded)" != stopped ]; do
    tries=$((tries + 1))
    [ "$tries" -le 10 ] || exit 1
    sleep 1
done
mount -o bind "$stage/vold" /system/bin/vold
mount -o bind "$stage/fstab.sun50iw9p1" /vendor/etc/fstab.sun50iw9p1
mount -o bind "$stage/rgsp-kmsg-start.sh" /vendor/bin/rgsp-kmsg-start.sh
touch "$stage/trial-active"
sh "$stage/rgsp-roms-handoff.sh" release
start rgsp-kmsg-bounded
start vold
sh "$stage/rgsp-roms-handoff.sh" mount
sm list-volumes all
