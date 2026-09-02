#!/bin/sh
set -eu

TF1_CID=1d414455534400002000009f9401a1e7
TF2_CID=fe3432534400000020000005bc01896b
ORIGINAL_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ORIGINAL_ENV_HEAD_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
SYSTEM_DEV=/dev/mmcblk1p2
SYSTEM_MOUNT=/mnt/rgsp-system-fix25
VERIFY_MOUNT=/mnt/rgsp-system-fix25-verify
BACKUP_DIR=/mnt/sdcard/RGSP_FIX25_BACKUP

test "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5
test "$(cat /sys/block/mmcblk0/device/cid)" = "$TF1_CID"
test "$(cat /sys/block/mmcblk1/device/cid)" = "$TF2_CID"
test "$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')" = "$ORIGINAL_BOOT_SHA"
test "$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')" = "$ORIGINAL_ENV_HEAD_SHA"
findmnt -rn -S "$SYSTEM_DEV" >/dev/null 2>&1 && exit 20
e2fsck -fn "$SYSTEM_DEV"

mkdir -p "$SYSTEM_MOUNT" "$VERIFY_MOUNT" "$BACKUP_DIR"
mount -t ext4 -o rw "$SYSTEM_DEV" "$SYSTEM_MOUNT"
trap 'mountpoint -q "$SYSTEM_MOUNT" && umount "$SYSTEM_MOUNT" || true' EXIT

replace_link() {
  source=$1
  destination=$2
  expected=$3
  test -f "$source"
  test "$(sha256sum "$source" | awk '{print $1}')" = "$expected"
  test -L "$destination"
  printf '%s -> %s\n' "$destination" "$(readlink "$destination")" >> "$BACKUP_DIR/replaced-links"
  rm "$destination"
  cp "$source" "$destination.fix25"
  chown 0:0 "$destination.fix25"
  chmod 0644 "$destination.fix25"
  mv "$destination.fix25" "$destination"
  test "$(sha256sum "$destination" | awk '{print $1}')" = "$expected"
}

replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib64/libandroidicu.so" "$SYSTEM_MOUNT/system/lib64/libandroidicu.so" 930651e8a696d28c5025acaebdac975d2d6e5b3b1882999ab2887b39d89a5f40
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib64/libnativebridge.so" "$SYSTEM_MOUNT/system/lib64/libnativebridge.so" 5ec6e3e6c4d229744b63669e670c88dbdbb3295bab29d01f6a177940cea17895
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib64/libnativehelper.so" "$SYSTEM_MOUNT/system/lib64/libnativehelper.so" 4b0edc40adb37b6d15858f9f278a6f340e56a69e375a57349796154a28177425
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib64/libnativeloader.so" "$SYSTEM_MOUNT/system/lib64/libnativeloader.so" 5fbf23f57422c161f4fd7ddadbf1226fe3ca10efb44146f10c9596e4d06309e0
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib64/libdexfile_external.so" "$SYSTEM_MOUNT/system/lib64/libdexfile_external.so" 9a359bb96ac30d6317b08b78bbbc83417816e67f80e80eb3bb9a46e7f76f33a8
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib/libandroidicu.so" "$SYSTEM_MOUNT/system/lib/libandroidicu.so" 3c73f5db164dfc99efd5c8729caaf80377e9ba0477c4bd6b9f13fa8a02755656
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib/libnativebridge.so" "$SYSTEM_MOUNT/system/lib/libnativebridge.so" a367f51ffdd115a2467440042dc5ef403c403c433d344ecd230c4a0332454492
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib/libnativehelper.so" "$SYSTEM_MOUNT/system/lib/libnativehelper.so" 85f774943b8a5390b530a2d85f35aea534bbe2aa4f92ca38794969ceb41377a5
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib/libnativeloader.so" "$SYSTEM_MOUNT/system/lib/libnativeloader.so" 382b941c743284e21e4bb501035a0effa2cb7274ed4d1dc245c4855b4bd6ab46
replace_link "$SYSTEM_MOUNT/system/apex/com.android.art.release/lib/libdexfile_external.so" "$SYSTEM_MOUNT/system/lib/libdexfile_external.so" c381f34d7503b98d3f43984bf34299f2155e2c5d53ff2516444f51c6a03df226
replace_link "$SYSTEM_MOUNT/system/apex/com.android.os.statsd/lib64/libstatssocket.so" "$SYSTEM_MOUNT/system/lib64/libstatssocket.so" e80469c14594c25ec19cf37c1cebcd68d5e5fc337815793306503f1f3c49ccd1
replace_link "$SYSTEM_MOUNT/system/apex/com.android.os.statsd/lib64/libstatspull.so" "$SYSTEM_MOUNT/system/lib64/libstatspull.so" b98e1c382d0a960d0bcbbc0eff0c9693fe02c4291a376d3886f308fdf5dde9aa
replace_link "$SYSTEM_MOUNT/system/apex/com.android.os.statsd/lib/libstatssocket.so" "$SYSTEM_MOUNT/system/lib/libstatssocket.so" 752aee8e74e8e0b4ac80a20cd89469efb7eefdbd900fdb205c7793c87cbc3f1c
replace_link "$SYSTEM_MOUNT/system/apex/com.android.os.statsd/lib/libstatspull.so" "$SYSTEM_MOUNT/system/lib/libstatspull.so" 3ae8b303e7cbfadddc0b19e33b598bf9c4c2b55e63a781d925bfe026aec4cdcb
replace_link "$SYSTEM_MOUNT/system/apex/com.android.adbd/lib64/libadb_protos.so" "$SYSTEM_MOUNT/system/lib64/libadb_protos.so" aeb9d306ab23f702bebc95cca49dad723f8f8340083ce5a47061a6639d4ee9e0

sync
umount "$SYSTEM_MOUNT"
trap - EXIT
e2fsck -fn "$SYSTEM_DEV"

mount -t ext4 -o ro "$SYSTEM_DEV" "$VERIFY_MOUNT"
trap 'mountpoint -q "$VERIFY_MOUNT" && umount "$VERIFY_MOUNT" || true' EXIT
test -f "$VERIFY_MOUNT/system/lib64/libnativeloader.so"
test ! -L "$VERIFY_MOUNT/system/lib64/libnativeloader.so"
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libnativeloader.so" | awk '{print $1}')" = 5fbf23f57422c161f4fd7ddadbf1226fe3ca10efb44146f10c9596e4d06309e0
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libstatssocket.so" | awk '{print $1}')" = e80469c14594c25ec19cf37c1cebcd68d5e5fc337815793306503f1f3c49ccd1
test "$(sha256sum "$VERIFY_MOUNT/system/lib64/libadb_protos.so" | awk '{print $1}')" = aeb9d306ab23f702bebc95cca49dad723f8f8340083ce5a47061a6639d4ee9e0
umount "$VERIFY_MOUNT"
trap - EXIT

{
  echo DATE=2026-08-29
  echo FIX=fix25
  echo PATCH_SEMANTICS='Replace fix24 APEX symlinks with verified regular files in system lib paths'
  cat "$BACKUP_DIR/replaced-links"
  echo TF1_BOOT_SHA="$(sha256sum /dev/mmcblk0p4 | awk '{print $1}')"
  echo ENV_HEAD_SHA="$(dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}')"
} | tee /mnt/sdcard/RGSP_ANDROID_FIX25_SYSTEM_PREP.log
