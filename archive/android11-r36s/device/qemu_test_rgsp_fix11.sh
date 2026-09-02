#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
IMAGE="$ROOT/out/rgsp-android11-alpha/rgsp-android11-system-alpha.img"
TEST_ROOT=/tmp/rgsp-qemu-root
QEMU_ROOT=/tmp/rgsp-qemu-host

test "$TEST_ROOT" = /tmp/rgsp-qemu-root
test "$QEMU_ROOT" = /tmp/rgsp-qemu-host
rm -rf "$TEST_ROOT" "$QEMU_ROOT"
mkdir -p "$TEST_ROOT" "$QEMU_ROOT"

debugfs -R "rdump / $TEST_ROOT" "$IMAGE"

cp /usr/bin/qemu-aarch64 "$TEST_ROOT/qemu-aarch64"
ldd /usr/bin/qemu-aarch64 | awk '/=> \// {print $3} /^\// {print $1}' | while read -r lib; do
  target="$TEST_ROOT$lib"
  mkdir -p "$(dirname "$target")"
  cp "$lib" "$target"
done
loader=$(ldd /usr/bin/qemu-aarch64 | awk '/ld-linux/ {print $1; exit}')
mkdir -p "$TEST_ROOT$(dirname "$loader")"
cp "$loader" "$TEST_ROOT$loader"

mkdir -p "$TEST_ROOT/dev" "$TEST_ROOT/proc" "$TEST_ROOT/sys" \
  "$TEST_ROOT/mnt" "$TEST_ROOT/debug_ramdisk" "$TEST_ROOT/rgsp-persist"

cp "$TEST_ROOT/system/lib64/libselinux.so" "$TEST_ROOT/system/lib64/libselinux.fix10.so"

run_case() {
  name=$1
  log="$ROOT/out/RGSP_QEMU_SECOND_STAGE_${name}.log"
  : > "$log"
  timeout 8 unshare -Urnm --propagation private sh -eu -c '
    root=$1
    mount -t proc proc "$root/proc"
    mount -t tmpfs -o mode=0755 tmpfs "$root/dev"
    mkdir -p "$root/dev/pts" "$root/dev/socket"
    mount -t devpts devpts "$root/dev/pts"
    mount -t sysfs -o ro sysfs "$root/sys"
    mount -t tmpfs -o mode=0755 tmpfs "$root/mnt"
    mount -t tmpfs -o mode=0755 tmpfs "$root/debug_ramdisk"
    exec chroot "$root" /qemu-aarch64 /system/bin/init second_stage
  ' sh "$TEST_ROOT" > "$log" 2>&1 || true
  printf '%s_LOG=%s\n' "$name" "$log"
  tail -n 80 "$log"
}

run_case original

# Return success immediately from the file-label functions. The RGSP kernel is
# booted with selinux=0, so these operations cannot enforce labels and only
# exercise an incompatible disabled-SELinux path in this imported userspace.
printf '\000\000\200\322\300\003\137\326' | dd of="$TEST_ROOT/system/lib64/libselinux.so" bs=1 seek=$((0x12a38)) conv=notrunc status=none
printf '\000\000\200\122\300\003\137\326' | dd of="$TEST_ROOT/system/lib64/libselinux.so" bs=1 seek=$((0x14748)) conv=notrunc status=none
printf '\300\003\137\326' | dd of="$TEST_ROOT/system/lib64/libselinux.so" bs=1 seek=$((0x14fe0)) conv=notrunc status=none

aarch64-linux-gnu-objdump -d --start-address=0x12a38 --stop-address=0x12a48 \
  "$TEST_ROOT/system/lib64/libselinux.so"
aarch64-linux-gnu-objdump -d --start-address=0x14748 --stop-address=0x14758 \
  "$TEST_ROOT/system/lib64/libselinux.so"
aarch64-linux-gnu-objdump -d --start-address=0x14fe0 --stop-address=0x14fec \
  "$TEST_ROOT/system/lib64/libselinux.so"

run_case patched

printf 'ORIGINAL_LIBSELINUX_SHA='
sha256sum "$TEST_ROOT/system/lib64/libselinux.fix10.so" | cut -d' ' -f1
printf 'PATCHED_LIBSELINUX_SHA='
sha256sum "$TEST_ROOT/system/lib64/libselinux.so" | cut -d' ' -f1
