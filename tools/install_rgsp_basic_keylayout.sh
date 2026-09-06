#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin
B=/rgsp-persist
SOURCE="$B/ANBERNIC-keys.kl"
TARGET_DIR=/system/usr/keylayout
BACKUP="$B/basic-keylayout-backup"
EXPECTED="${1:?expected keylayout SHA256 required}"

[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop sys.boot_completed)" = 1 ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7 ]
[ "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b ]
[ "$(sha256sum /dev/block/mmcblk0p4 | cut -d ' ' -f 1)" = d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5 ]
[ "$(dd if=/dev/block/mmcblk0p3 bs=131072 count=1 2>/dev/null | sha256sum | cut -d ' ' -f 1)" = d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396 ]
[ "$(sha256sum "$SOURCE" | cut -d ' ' -f 1)" = "$EXPECTED" ]
[ "$(sha256sum /vendor/lib/hw/hwcomposer.cupid.so | cut -d ' ' -f 1)" = 89a1f16c3b2b03b3f3250c77f1cae3d35a9995a44281a7538307d8fbbb7fecf2 ]
grep -q '^/dev/mmcblk1p3 /vendor ext4 ro,' /proc/mounts
mkdir -p "$BACKUP"
if [ ! -f "$BACKUP/baseline.txt" ]; then
    if [ -e "$TARGET_DIR/Vendor_0001_Product_0001_Version_0100.kl" ]; then
        cp "$TARGET_DIR/Vendor_0001_Product_0001_Version_0100.kl" "$BACKUP/ANBERNIC-keys.kl"
    else
        touch "$BACKUP/target-was-absent"
    fi
    dumpsys input > "$BACKUP/input-before.txt"
    { date; cat /proc/uptime; pidof surfaceflinger system_server; } > "$BACKUP/baseline.txt"
fi

mount -o remount,rw /
trap 'sync; mount -o remount,ro /' EXIT
mkdir -p "$TARGET_DIR"
for name in \
    Vendor_0001_Product_0001_Version_0100.kl \
    Vendor_0001_Product_0001.kl \
    ANBERNIC-keys.kl; do
    target="$TARGET_DIR/$name"
    cp "$SOURCE" "$target.new"
    chmod 0644 "$target.new"
    chown root:root "$target.new"
    [ "$(sha256sum "$target.new" | cut -d ' ' -f 1)" = "$EXPECTED" ]
    mv "$target.new" "$target"
done
restorecon -R /vendor/usr
sync
mount -o remount,ro /
trap - EXIT
sha256sum "$TARGET_DIR/Vendor_0001_Product_0001_Version_0100.kl"
echo RGSP_BASIC_KEYLAYOUT_INSTALLED_RESTART_PENDING
