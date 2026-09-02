#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$2" != "--confirm-mmCblk1-system" ]; then
  echo "usage: $0 /path/to/rgsp-android11-system-alpha.img.gz --confirm-mmCblk1-system" >&2
  exit 64
fi

ARCHIVE=$1
DEV=/dev/mmcblk1
BOOT_PART=${DEV}p1
SYSTEM_PART=${DEV}p2
EXPECTED_BOOT_PARTUUID=0720745f-bbfb-4940-bef7-8595c6f34f4b
EXPECTED_SYSTEM_PARTUUID=096d7fa1-62e8-c242-9876-cfdd5a92b8eb
EXPECTED_IMAGE_BYTES=2365268480

[ -f "$ARCHIVE" ] || { echo "missing archive: $ARCHIVE" >&2; exit 2; }
[ -b "$DEV" ] || { echo "missing TF2 device: $DEV" >&2; exit 3; }
[ -b "$BOOT_PART" ] || { echo "missing TF2 boot partition" >&2; exit 4; }
[ -b "$SYSTEM_PART" ] || { echo "missing TF2 system partition" >&2; exit 5; }

SIZE=$(blockdev --getsize64 "$DEV")
[ "$SIZE" -ge 120000000000 ] || {
  echo "refusing unexpected TF2 size: $SIZE" >&2
  exit 6
}

boot_uuid=$(blkid -s PARTUUID -o value "$BOOT_PART")
system_uuid=$(blkid -s PARTUUID -o value "$SYSTEM_PART")
[ "$boot_uuid" = "$EXPECTED_BOOT_PARTUUID" ] || {
  echo "refusing unexpected boot PARTUUID: $boot_uuid" >&2
  exit 7
}
[ "$system_uuid" = "$EXPECTED_SYSTEM_PARTUUID" ] || {
  echo "refusing unexpected system PARTUUID: $system_uuid" >&2
  exit 8
}

if findmnt -rn -S "$SYSTEM_PART" >/dev/null 2>&1; then
  echo "refusing: $SYSTEM_PART is mounted" >&2
  exit 9
fi

gzip -t "$ARCHIVE"
archive_bytes=$(gzip -dc "$ARCHIVE" | wc -c)
[ "$archive_bytes" -eq "$EXPECTED_IMAGE_BYTES" ] || {
  echo "refusing unexpected uncompressed size: $archive_bytes" >&2
  exit 10
}

echo "WRITING ANDROID SYSTEM ONLY TO $SYSTEM_PART"
echo "No mmcblk0 partition will be written."
sync
gzip -dc "$ARCHIVE" | dd of="$SYSTEM_PART" bs=4M conv=fsync
e2fsck -fy "$SYSTEM_PART"
resize2fs "$SYSTEM_PART"
sync

mkdir -p /mnt/android-boot
if ! findmnt -rn -S "$BOOT_PART" >/dev/null 2>&1; then
  mount "$BOOT_PART" /mnt/android-boot
fi

echo "system image installed; copy ANBOOT files to /mnt/android-boot separately"
echo "do not modify mmcblk0 or save U-Boot environment variables"

