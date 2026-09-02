#!/usr/bin/env bash
set -euo pipefail

mode=${1:?mode is required}
android_archive=${2:?Android archive is required}
longan_archive=${3:?Longan archive is required}
overlay=${4:?overlay is required}
requested=${5:?destination is required}
android_expected=${6:?expected Android MD5 is required}
longan_expected=${7:?expected Longan MD5 is required}
skip_hash=${8:-false}

case "$requested" in
  '~') dest=$HOME ;;
  '~/'*) dest="$HOME/${requested#'~/'}" ;;
  /*) dest=$requested ;;
  *) echo "Destination must be an absolute path or start with ~/: $requested" >&2; exit 19 ;;
esac

dest=$(realpath -m "$dest")
parent=$(dirname "$dest")
mkdir -p "$parent"
available_kib=$(df -Pk "$parent" | awk 'NR==2 {print $4}')

printf 'ANDROID_ARCHIVE=%s\nLONGAN_ARCHIVE=%s\nOVERLAY=%s\nDESTINATION=%s\nAVAILABLE_GIB=%s\n' \
  "$android_archive" "$longan_archive" "$overlay" "$dest" "$((available_kib / 1024 / 1024))"

if [ -e "$dest" ] && [ "$(find "$dest" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
  state=non-empty
else
  state=ready
fi
printf 'DESTINATION_STATE=%s\n' "$state"

if [ "$mode" = preview ]; then
  exit 0
fi
if [ "$mode" != execute ]; then
  echo "Unsupported mode: $mode" >&2
  exit 18
fi
if [ "$state" != ready ]; then
  echo "Refusing to overwrite non-empty destination: $dest" >&2
  exit 20
fi

required_kib=$((120 * 1024 * 1024))
if [ "$available_kib" -lt "$required_kib" ]; then
  echo "At least 120 GiB free space is required in the WSL filesystem." >&2
  exit 21
fi
if [ "$skip_hash" != true ]; then
  android_actual=$(md5sum "$android_archive" | awk '{print $1}')
  longan_actual=$(md5sum "$longan_archive" | awk '{print $1}')
  if [ "$android_actual" != "$android_expected" ]; then
    echo "H616 Android source MD5 mismatch: $android_actual" >&2
    exit 22
  fi
  if [ "$longan_actual" != "$longan_expected" ]; then
    echo "H616 Longan source MD5 mismatch: $longan_actual" >&2
    exit 23
  fi
fi

mkdir -p "$dest"
tar -xzf "$android_archive" -C "$dest"
tar -xzf "$longan_archive" -C "$dest"
mkdir -p "$dest/android/device"
rm -rf "$dest/android/device/roc"
cp -a "$overlay" "$dest/android/device/roc"
cat > "$dest/H700_ANDROID10_BASELINE.txt" <<EOF
H616_ANDROID_ARCHIVE_MD5=$android_expected
H616_LONGAN_ARCHIVE_MD5=$longan_expected
H700_OVERLAY_SOURCE=$overlay
PREPARED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
printf 'PREPARED_SOURCE=%s/android\n' "$dest"
