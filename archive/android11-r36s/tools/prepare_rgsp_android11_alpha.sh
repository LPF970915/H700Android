#!/bin/sh
set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 SYSTEM_IMAGE MOUNT_DIR ASSET_DIR" >&2
  exit 64
fi

IMAGE=$(readlink -f "$1")
MOUNT_DIR=$(readlink -f "$2")
ASSET_DIR=$(readlink -f "$3")

[ -f "$IMAGE" ] || { echo "missing image: $IMAGE" >&2; exit 2; }
[ -d "$MOUNT_DIR" ] || { echo "missing mount dir: $MOUNT_DIR" >&2; exit 3; }
[ -f "$ASSET_DIR/fstab.rgsp" ] || { echo "missing RGSP assets" >&2; exit 4; }

cleanup() {
  if mountpoint -q "$MOUNT_DIR"; then
    umount "$MOUNT_DIR"
  fi
}
trap cleanup EXIT INT TERM

e2fsck -fy "$IMAGE"
mount -o loop,rw "$IMAGE" "$MOUNT_DIR"

install -o 0 -g 0 -m 0644 "$ASSET_DIR/fstab.rgsp" "$MOUNT_DIR/fstab.rgsp"
install -o 0 -g 0 -m 0644 "$ASSET_DIR/init.rgsp.rc" "$MOUNT_DIR/init.rgsp.rc"
install -o 0 -g 0 -m 0644 "$ASSET_DIR/ueventd.rgsp.rc" "$MOUNT_DIR/ueventd.rgsp.rc"
install -o 0 -g 0 -m 0644 "$ASSET_DIR/RGSP_ANDROID_ALPHA.txt" "$MOUNT_DIR/RGSP_ANDROID_ALPHA.txt"
install -o 0 -g 0 -m 0644 "$ASSET_DIR/fstab.rgsp" "$MOUNT_DIR/system/vendor/fstab.rgsp"

disable_rc() {
  path="$MOUNT_DIR/$1"
  if [ -f "$path" ]; then
    mv "$path" "$path.rk3326-disabled"
  fi
}

disable_rc init.rk30board.rc
disable_rc ueventd.rk30board.rc
disable_rc system/etc/init/surfaceflinger.rc
disable_rc system/etc/init/bootanim.rc
disable_rc system/vendor/etc/init/hw/init.rk30board.rc
disable_rc system/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc
disable_rc system/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc
disable_rc system/vendor/etc/init/android.hardware.audio.service.rc
disable_rc system/vendor/etc/init/android.hardware.power@1.0-service.rc
disable_rc system/vendor/etc/init/android.hardware.light@2.0-service.rc
disable_rc system/vendor/etc/init/android.hardware.wifi@1.0-service.rc

for prop in "$MOUNT_DIR/system/build.prop" "$MOUNT_DIR/system/vendor/build.prop"; do
  [ -f "$prop" ] || continue
  sed -i \
    -e 's/LineageOS on GameConsole R36S/RGSP H700 Android Alpha/g' \
    -e 's/=r36s$/=rgsp/g' \
    -e 's/ro.board.platform=rk3326/ro.board.platform=sun50iw9/' \
    -e 's/^ro.hardware.vulkan=rk30board/# ro.hardware.vulkan disabled for RGSP alpha/' \
    -e 's/android-rockchip/android-allwinner/' \
    "$prop"
  if ! grep -q '^ro.config.low_ram=' "$prop"; then
    printf '\nro.config.low_ram=true\nro.rgsp.alpha=true\n' >> "$prop"
  fi
done

DEFAULT_PROP="$MOUNT_DIR/system/etc/prop.default"
sed -i \
  -e 's/^ro.secure=.*/ro.secure=0/' \
  -e 's/^ro.debuggable=.*/ro.debuggable=1/' \
  -e 's/^ro.adb.secure=.*/ro.adb.secure=0/' \
  -e 's/^persist.sys.usb.config=.*/persist.sys.usb.config=adb/' \
  -e 's/android-rockchip/android-allwinner/' \
  "$DEFAULT_PROP"

sync
umount "$MOUNT_DIR"
trap - EXIT INT TERM
e2fsck -fy "$IMAGE"
tune2fs -L RGSP_ANDROID_ALPHA "$IMAGE"

echo "prepared: $IMAGE"

