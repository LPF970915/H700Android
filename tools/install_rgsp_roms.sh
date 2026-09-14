#!/system/bin/sh
# Persist the already trialled storage components, keeping original files on data.
set -eu
export PATH=/system/bin:/vendor/bin
stage=/data/local/tmp/rgsp-roms-v1
[ "$(id -u)" = 0 ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]
[ "$(cat /sys/class/block/mmcblk0p8/start)" = 54960128 ]
[ "$(sha256sum "$stage/vold" | cut -d ' ' -f 1)" = "${1:?vold SHA256}" ]
[ "$(sha256sum "$stage/services.jar" | cut -d ' ' -f 1)" = "${2:?services SHA256}" ]
cd "$stage"
sha256sum -c install.sha256
[ ! -e "$stage/persisted" ]
backup=$stage/installed-originals
mkdir "$backup"
chmod 0700 "$backup"
finish() {
    rc=$?
    trap - EXIT
    sync
    mount -o remount,ro /vendor || rc=1
    mount -o remount,ro / || rc=1
    start rgsp-kmsg-bounded
    start vold
    start zygote
    echo "INSTALL_EXIT=$rc"
    exit "$rc"
}
trap finish EXIT
stop zygote
stop vold
stop rgsp-kmsg-bounded
tries=0
while [ "$(getprop init.svc.zygote)" != stopped ] ||
      [ "$(getprop init.svc.vold)" != stopped ] ||
      [ "$(getprop init.svc.rgsp-kmsg-bounded)" != stopped ]; do
    tries=$((tries + 1))
    [ "$tries" -le 15 ] || exit 1
    sleep 1
done
for target in /system/bin/vold /vendor/etc/fstab.sun50iw9p1 /vendor/bin/rgsp-kmsg-start.sh; do
    if awk -v p="$target" '$5==p {found=1} END {exit !found}' /proc/self/mountinfo; then
        # Only remove this trial's known per-file overlays.
        awk -v p="$target" '$5==p && $4 !~ /^\/local\/tmp\/rgsp-roms-v1\// {bad=1}
            END {exit bad}' /proc/self/mountinfo
        umount "$target"
    fi
done
mount -o remount,rw /
mount -o remount,rw /vendor
install_file() {
    source=$1
    target=$2
    mode=$3
    [ ! -L "$target" ]
    [ ! -e "$target.rgsp-roms-new" ]
    if [ -f "$target" ]; then
        cp -p "$target" "$backup/${target##*/}"
    else
        touch "$backup/${target##*/}.absent"
    fi
    cp "$stage/$source" "$target.rgsp-roms-new"
    chown 0:0 "$target.rgsp-roms-new"
    chmod "$mode" "$target.rgsp-roms-new"
    mv "$target.rgsp-roms-new" "$target"
    restorecon "$target"
    [ "$(sha256sum "$target" | cut -d ' ' -f 1)" = \
      "$(sha256sum "$stage/$source" | cut -d ' ' -f 1)" ]
}
install_file vold /system/bin/vold 0755
install_file services.jar /system/framework/services.jar 0644
install_file rgsp-roms-handoff.sh /system/bin/rgsp-roms-handoff.sh 0755
install_file rgsp-roms-handoff.rc /system/etc/init/rgsp-roms-handoff.rc 0644
install_file rgsp-kmsg-start.sh /vendor/bin/rgsp-kmsg-start.sh 0755
# Publish the disk source only after the protected backend is installed.
install_file fstab.sun50iw9p1 /vendor/etc/fstab.sun50iw9p1 0644
touch "$stage/persisted"
echo "ROMS_COMPONENTS_PERSISTED"
