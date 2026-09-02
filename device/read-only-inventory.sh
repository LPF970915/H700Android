#!/bin/sh
set -eu

# Run manually over SSH after reviewing every command. This script is read-only.
echo '=== identity ==='
cat /mnt/vendor/oem/board.ini 2>/dev/null || true
uname -a
cat /proc/device-tree/model 2>/dev/null || true
echo '=== partitions ==='
lsblk -o NAME,SIZE,FSTYPE,LABEL,PARTLABEL,MOUNTPOINT 2>/dev/null || cat /proc/partitions
echo '=== boot image ==='
file -s /dev/mmcblk0p4
sha256sum /dev/mmcblk0p4
echo '=== boot config ==='
zcat /proc/config.gz 2>/dev/null | grep -E 'CONFIG_(ANDROID|ANDROID_BINDER|ASHMEM|ION|FB|DRM)' || true
echo '=== display nodes ==='
ls -l /dev/fb0 /dev/disp /dev/ion /dev/mali0 2>/dev/null || true
echo '=== input/audio ==='
cat /proc/bus/input/devices
cat /proc/asound/cards 2>/dev/null || true
echo '=== u-boot strings ==='
strings /dev/mmcblk0p3 2>/dev/null | grep -E 'boot_(normal|recovery|fastboot)|setargs_' || true
