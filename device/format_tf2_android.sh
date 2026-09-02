#!/bin/sh
set -eu

# Destructive by design: this script is only for the explicitly replaceable
# TF2 card. It refuses every device except a 125 GB-class mmcblk1 mounted at
# /mnt/sdcard before repartitioning.
[ "${1:-}" = "--confirm-mmCblk1" ] || {
  echo "usage: $0 --confirm-mmCblk1" >&2
  exit 64
}

DEV=/dev/mmcblk1
PART=/dev/mmcblk1p1
[ -b "$DEV" ] || { echo "missing $DEV" >&2; exit 2; }
[ "$(basename "$(readlink -f /sys/class/block/mmcblk1/device/block/mmcblk1 2>/dev/null || true)")" = "mmcblk1" ] || {
  echo "refusing: mmcblk1 identity check failed" >&2
  exit 3
}
SIZE=$(blockdev --getsize64 "$DEV")
[ "$SIZE" -ge 120000000000 ] || { echo "refusing: unexpected TF2 size $SIZE" >&2; exit 4; }
TARGET=$(findmnt -n -o TARGET "$PART" 2>/dev/null || true)
case "$TARGET" in
  /mnt/sdcard|"") ;;
  *) echo "refusing: $PART is mounted at unexpected target '$TARGET'" >&2; exit 5 ;;
esac

echo "ERASING ONLY $DEV ($SIZE bytes)"
sync
umount /mnt/sdcard 2>/dev/null || true
sleep 1
if findmnt -rn -S "$PART" >/dev/null 2>&1; then
  umount -l /mnt/sdcard
  sleep 1
fi
if findmnt -rn -S "$PART" >/dev/null 2>&1; then
  echo "refusing: $PART is still mounted after unmount" >&2
  exit 6
fi

# 1 MiB alignment. p5 intentionally consumes the remainder.
cat <<'EOF' | sfdisk --wipe always "$DEV"
label: gpt
unit: sectors

start=2048, size=524288, type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name="ANDROID_BOOT"
size=16777216, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, name="ANDROID_SYSTEM"
size=4194304, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, name="ANDROID_VENDOR"
size=33554432, type=0FC63DAF-8483-4772-8E79-3D69D8477DE4, name="ANDROID_DATA"
type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name="SHARED_ROMS"
EOF

partprobe "$DEV"
udevadm settle 2>/dev/null || true
sleep 2

if findmnt -rn -S "$PART" >/dev/null 2>&1; then
  echo "refusing: automounter remounted $PART during repartition" >&2
  exit 7
fi

mkfs.vfat -F 32 -n ANBOOT "$DEV"p1
mkfs.ext4 -F -m 0 -L ANDROID_SYSTEM "$DEV"p2
mkfs.ext4 -F -m 0 -L ANDROID_VENDOR "$DEV"p3
mkfs.ext4 -F -m 0 -L ANDROID_DATA "$DEV"p4
mkfs.vfat -F 32 -n ROMS "$DEV"p5

mkdir -p /mnt/android-boot /mnt/android-system /mnt/android-vendor /mnt/android-data /mnt/sdcard
mount "$DEV"p1 /mnt/android-boot
mount "$DEV"p5 /mnt/sdcard
echo "TF2 repartitioned and formatted"
lsblk -o NAME,SIZE,FSTYPE,LABEL,PARTLABEL,MOUNTPOINT "$DEV"
