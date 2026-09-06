#!/bin/sh
set -u

exec </dev/console >/dev/console 2>&1

mount -t proc proc /proc 2>/dev/null || true
mount -t sysfs sysfs /sys 2>/dev/null || true
mount -t devtmpfs devtmpfs /dev 2>/dev/null || true
mkdir -p /dev/pts /dev/socket /android-root /rgsp-boot
mount -t devpts devpts /dev/pts 2>/dev/null || true
echo 10 > /proc/sys/kernel/panic 2>/dev/null || true
echo 0 > /proc/sys/kernel/printk_ratelimit 2>/dev/null || true

BOOT_DEV=/dev/mmcblk1p1
SYSTEM_DEV=/dev/mmcblk1p2
VENDOR_DEV=/dev/mmcblk1p3
DATA_DEV=/dev/mmcblk1p4
LINUX_BOOT_DEV=/dev/mmcblk0p4
LINUX_BOOT_IMAGE=/rgsp-boot/rgsp-linux-boot-original.img
LINUX_BOOT_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
HANDOFF_VERSION=a10-b3-fix66-data-mali-static-verified-watchdog
BOOT_MOUNTED=0
LINUX_BOOT_RESTORED=0
LOG=/dev/null

log() {
  echo "$*"
  if [ "$LOG" != /dev/null ]; then
    echo "$*" >> "$LOG" 2>/dev/null || true
    sync
  fi
}

fail_reboot() {
  log "[rgsp-android] ERROR: $*"
  if [ "$LINUX_BOOT_RESTORED" -eq 1 ]; then
    log '[rgsp-android] rebooting into the restored TF1 Linux boot image'
    sleep 5
    /bin/busybox reboot -f
    sleep 30
  fi
  log '[rgsp-android] TF1 boot was not restored; refusing an automatic reboot loop'
  exec /bin/ash
}

echo '[rgsp-android] handoff init reached'
tries=0
while { [ ! -b "$BOOT_DEV" ] || [ ! -b "$SYSTEM_DEV" ] || [ ! -b "$VENDOR_DEV" ] || [ ! -b "$DATA_DEV" ] || [ ! -b "$LINUX_BOOT_DEV" ]; } && [ "$tries" -lt 30 ]; do
  echo "[rgsp-android] waiting for TF2 devices ($tries/30)"
  sleep 1
  tries=$((tries + 1))
done

if [ -b "$BOOT_DEV" ] && mount -t vfat -o rw "$BOOT_DEV" /rgsp-boot; then
  BOOT_MOUNTED=1
  LOG=/rgsp-boot/RGSP_ANDROID_BOOT_LAST.log
  : > "$LOG"
  log '[rgsp-android] persistent log opened'
  log "[rgsp-android] handoff version: $HANDOFF_VERSION"
  log "[rgsp-android] date: $(date 2>/dev/null || true)"
  log "[rgsp-android] cmdline: $(cat /proc/cmdline 2>/dev/null || true)"
  log "[rgsp-android] devices: $(ls /dev/mmcblk* 2>/dev/null || true)"
else
  echo '[rgsp-android] ERROR: unable to mount TF2 boot partition for recovery and logging'
  exec /bin/ash
fi

if [ ! -f "$LINUX_BOOT_IMAGE" ]; then
  fail_reboot "missing TF1 boot recovery image: $LINUX_BOOT_IMAGE"
fi

SOURCE_SHA=$(/bin/busybox sha256sum "$LINUX_BOOT_IMAGE" 2>/dev/null | /bin/busybox awk '{print $1}')
if [ "$SOURCE_SHA" != "$LINUX_BOOT_SHA" ]; then
  fail_reboot "TF1 boot recovery image hash mismatch: $SOURCE_SHA"
fi

log '[rgsp-android] restoring the original TF1 Linux boot image before Android handoff'
if ! dd if="$LINUX_BOOT_IMAGE" of="$LINUX_BOOT_DEV" bs=1M >> "$LOG" 2>&1; then
  fail_reboot "failed to restore $LINUX_BOOT_DEV"
fi
sync
TARGET_SHA=$(/bin/busybox sha256sum "$LINUX_BOOT_DEV" 2>/dev/null | /bin/busybox awk '{print $1}')
if [ "$TARGET_SHA" != "$LINUX_BOOT_SHA" ]; then
  fail_reboot "restored TF1 boot hash mismatch: $TARGET_SHA"
fi
LINUX_BOOT_RESTORED=1
log '[rgsp-android] original TF1 Linux boot image restored and verified'

if [ -f /rgsp-boot/RGSP_ANDROID_TRY.ONCE ]; then
  rm -f /rgsp-boot/RGSP_ANDROID_TRY.ONCE
  log '[rgsp-android] one-shot marker consumed'
else
  log '[rgsp-android] one-shot marker absent; returning directly to TF1 Linux'
  fail_reboot 'Android one-shot request is absent'
fi

if [ ! -b "$SYSTEM_DEV" ] || [ ! -b "$VENDOR_DEV" ] || [ ! -b "$DATA_DEV" ]; then
  fail_reboot "missing Android partitions: system=$SYSTEM_DEV vendor=$VENDOR_DEV data=$DATA_DEV"
fi

if ! mount -t ext4 -o ro "$SYSTEM_DEV" /android-root; then
  fail_reboot "failed to mount Android system from $SYSTEM_DEV"
fi

if ! mount -t ext4 -o ro "$VENDOR_DEV" /android-root/vendor; then
  fail_reboot "failed to mount Android vendor from $VENDOR_DEV"
fi
log '[rgsp-android] Android vendor mounted at /vendor'

mkdir -p /android-root/data || fail_reboot 'failed to create Android /data mount point'
if ! mount -t ext4 -o rw,noatime,nosuid,nodev,noauto_da_alloc "$DATA_DEV" /android-root/data; then
  fail_reboot "failed to mount Android data from $DATA_DEV"
fi
log '[rgsp-android] Android data mounted read-write at /data'

if [ ! -x /android-root/system/bin/init ]; then
  umount /android-root 2>/dev/null || true
  fail_reboot 'Android /system/bin/init is missing or not executable'
fi

if [ ! -d /android-root/system/apex ] || [ ! -d /android-root/apex ]; then
  fail_reboot 'Android flattened APEX directories are missing'
fi
if ! mount -t tmpfs -o mode=0755,nosuid,nodev,noexec tmpfs /android-root/apex; then
  fail_reboot 'failed to create writable Android APEX mount root'
fi
log '[rgsp-android] writable APEX tmpfs mounted; apexd-bootstrap will activate flattened packages'

# Android 10 does not ship the later diagnostic mount point in its system
# image. Create it before binding the TF2 ANBOOT volume so the same persistent
# UART/logging path works for both the handoff ramdisk and second-stage init.
mkdir -p /android-root/rgsp-persist || fail_reboot 'failed to create /rgsp-persist in Android root'

log '[rgsp-android] Android root mounted; preparing switch_root'
if ! /bin/busybox mount -o bind /dev /android-root/dev; then
  fail_reboot 'failed to bind /dev under Android root'
fi
for binder_node in binder hwbinder vndbinder; do
  node=/android-root/dev/$binder_node
  [ -c "$node" ] || fail_reboot "missing inherited Binder device: $node"
  /bin/busybox chown 0:0 "$node" || fail_reboot "failed to chown $node"
  /bin/busybox chmod 0666 "$node" || fail_reboot "failed to chmod $node"
done
log '[rgsp-android] inherited Binder device permissions set to 0666 root:root'
for graphics_node in ion mali0 disp fb0 g2d; do
  node=/android-root/dev/$graphics_node
  [ -c "$node" ] || continue
  /bin/busybox chown 1000:1003 "$node" || fail_reboot "failed to chown $node"
  /bin/busybox chmod 0660 "$node" || fail_reboot "failed to chmod $node"
done
mkdir -p /android-root/dev/graphics || fail_reboot 'failed to create /dev/graphics'
if [ -c /android-root/dev/fb0 ]; then
  /bin/busybox rm -f /android-root/dev/graphics/fb0 2>/dev/null || true
  /bin/busybox ln -s /dev/fb0 /android-root/dev/graphics/fb0 || fail_reboot 'failed to link /dev/graphics/fb0'
  log '[rgsp-android] inherited fb0 exists; /dev/graphics/fb0 alias created'
else
  log '[rgsp-android] inherited fb0 is not present before switch_root'
fi
log '[rgsp-android] inherited graphics device permissions set to 0660 system:graphics'
mkdir -p /android-root/dev/block/by-partuuid || fail_reboot 'failed to create Android block-device links directory'
for block_spec in \
  096d7fa1-62e8-c242-9876-cfdd5a92b8eb:mmcblk1p2 \
  6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8:mmcblk1p3 \
  734716ed-e7d9-e74f-9b3e-4f1cb8d448ed:mmcblk1p4; do
  uuid=${block_spec%%:*}
  device=${block_spec#*:}
  /bin/busybox ln -snf "/dev/$device" "/android-root/dev/block/by-partuuid/$uuid" || fail_reboot "failed to link PARTUUID $uuid"
done
log '[rgsp-android] Android PARTUUID links created for system, vendor, and data'
if ! /bin/busybox mount -o bind /proc /android-root/proc; then
  fail_reboot 'failed to bind /proc under Android root'
fi
if ! /bin/busybox mount -o bind /sys /android-root/sys; then
  fail_reboot 'failed to bind /sys under Android root'
fi
# Android first-stage init normally mounts selinuxfs before it execs
# /system/bin/init selinux_setup. Mount it inside the new root after binding
# /sys; a plain bind does not carry /sys submounts into /android-root/sys.
mkdir -p /android-root/sys/fs/selinux
if ! mountpoint -q /android-root/sys/fs/selinux; then
  mount -t selinuxfs selinuxfs /android-root/sys/fs/selinux || fail_reboot 'failed to mount selinuxfs in Android root'
fi
test -e /android-root/sys/fs/selinux/load || fail_reboot 'Android-root selinuxfs load node is missing'
log '[rgsp-android] selinuxfs mounted in Android root and policy load node is present'
if ! mount -t tmpfs -o mode=0755 tmpfs /android-root/mnt; then
  fail_reboot 'failed to mount Android /mnt tmpfs'
fi
if ! mount -t tmpfs -o mode=0755 tmpfs /android-root/debug_ramdisk; then
  fail_reboot 'failed to mount Android debug ramdisk tmpfs'
fi
if [ "$BOOT_MOUNTED" -eq 1 ]; then
  if [ ! -d /android-root/rgsp-persist ]; then
    fail_reboot 'missing persistent mount point in Android root: /rgsp-persist'
  fi
  /bin/busybox mount -o bind /rgsp-boot /android-root/rgsp-persist || fail_reboot 'failed to bind boot-log partition at /rgsp-persist'
fi

KMSG_LOG=/rgsp-boot/RGSP_ANDROID_KMSG_LAST.log
: > "$KMSG_LOG" || fail_reboot 'failed to create persistent Android kmsg log'
chmod 0666 "$KMSG_LOG" 2>/dev/null || true
/bin/busybox cat /dev/kmsg >> "$KMSG_LOG" 2>&1 &
sleep 1
log '[rgsp-android] persistent Android kernel-log reader started'

# switch_root removes the old ramdisk executables and moves the Android root.
# Keep a static helper on the inherited devtmpfs; resolve Android via PID 1.
mkdir -p /android-root/dev/rgsp
cp /android-root/vendor/bin/busybox /android-root/dev/rgsp/busybox || fail_reboot 'failed to preserve static watchdog helper'
chmod 0700 /android-root/dev/rgsp/busybox
/android-root/dev/rgsp/busybox true || fail_reboot 'watchdog helper self-test failed'

# Track Android processes dynamically because Binder failure PIDs change on
# every boot. This process stays in the handoff root after switch_root.
PROC_LOG=/rgsp-boot/RGSP_ANDROID_PROC_LAST.log
: > "$PROC_LOG" || fail_reboot 'failed to create persistent Android process log'
chmod 0666 "$PROC_LOG" 2>/dev/null || true
(
  exec 3>> "$PROC_LOG"

  wait_one_second() {
    IFS=' ' read -r now ignored < /proc/uptime || return
    deadline=$(( ${now%%.*} + 1 ))
    /dev/rgsp/busybox sleep 1 2>/dev/null || true
    # Keep the timer bounded by real uptime even if the helper cannot exec.
    while :; do
      IFS=' ' read -r now ignored < /proc/uptime || return
      [ "${now%%.*}" -ge "$deadline" ] && return
    done
  }

  android_getprop() {
    if [ -x /proc/1/root/system/bin/getprop ]; then
      /dev/rgsp/busybox chroot /proc/1/root /system/bin/getprop "$1" 2>/dev/null || true
    fi
  }

  android_framework_ready() {
    sf=
    ss=
    launcher=
    systemui=
    for p in /proc/[0-9]*; do
      comm=
      IFS= read -r comm < "$p/comm" 2>/dev/null || continue
      case "$comm" in
        surfaceflinger) sf=${p##*/} ;;
        system_server) ss=${p##*/} ;;
        droid.launcher3) launcher=${p##*/} ;;
        ndroid.systemui) systemui=${p##*/} ;;
      esac
    done
    signature="$sf:$ss:$launcher:$systemui"
    [ -n "$sf" ] && [ -n "$ss" ] && [ -n "$launcher" ] && [ -n "$systemui" ]
  }

  i=0
  stable=0
  previous=
  while [ "$i" -lt 600 ]; do
    {
      echo "=== process snapshot $i ==="
      IFS=' ' read -r uptime ignored < /proc/uptime || uptime=unknown
      echo "uptime=$uptime"
      for p in /proc/[0-9]*; do
        pid=${p##*/}
        comm=
        IFS= read -r comm < "$p/comm" 2>/dev/null || continue
        case "$comm" in
          surfaceflinger|system_server|droid.launcher3|ndroid.systemui|bootanimation) ;;
          *) continue ;;
        esac
        status=
        while IFS= read -r line; do
          case "$line" in
            Name:*|State:*|PPid:*|Uid:*|Gid:*|Threads:*) status="${status}${line};" ;;
          esac
        done < "$p/status" 2>/dev/null || true
        printf 'pid=%s comm=%s status=%s\n' "$pid" "$comm" "$status"
      done
    } >&3 2>/dev/null || true
    boot_completed=$(android_getprop sys.boot_completed)
    if android_framework_ready && [ "$signature" = "$previous" ] && [ "$boot_completed" = 1 ]; then
      stable=$((stable + 1))
    else
      stable=0
    fi
    previous=$signature
    echo "boot_completed=$boot_completed stable_seconds=$stable pids=$signature" >&3
    if [ "$stable" -ge 120 ]; then
      echo '=== boot completed and same framework PIDs for 120s; watchdog exits (visual verification still required) ===' >&3
      exit 0
    fi
    i=$((i + 1))
    wait_one_second
  done
  if [ "$stable" -lt 120 ]; then
    echo '=== process capture complete without boot completion; sysrq sync and Linux reboot requested ===' >&3
    if [ -w /proc/sysrq-trigger ]; then
      printf s > /proc/sysrq-trigger
      wait_one_second
      wait_one_second
      printf u > /proc/sysrq-trigger
      wait_one_second
      wait_one_second
      printf b > /proc/sysrq-trigger
    fi
    echo '=== automatic sysrq reboot unavailable ===' >&3
  fi
) &
PROC_SCANNER_PID=$!
log "[rgsp-android] process watchdog started: pid=$PROC_SCANNER_PID timeout=600s; requires boot completion and unchanged framework PIDs for 120s"

INIT_LOG=/rgsp-boot/RGSP_ANDROID_INIT_LAST.log
: > "$INIT_LOG" || fail_reboot 'failed to create persistent Android init log'
chmod 0666 "$INIT_LOG" 2>/dev/null || true
log '[rgsp-android] Android init will use live /dev/kmsg; background reader captures it'

INIT_STARTED_AT=$(/bin/busybox awk '{printf "%d", $1 * 1000}' /proc/uptime)
INIT_SELINUX_TOOK=0
export INIT_STARTED_AT INIT_SELINUX_TOOK
log "[rgsp-android] second-stage environment: init=${INIT_STARTED_AT}ms selinux=${INIT_SELINUX_TOOK}ms"

: > /android-root/dev/.coldboot_done || fail_reboot 'failed to mark inherited devtmpfs ready'
chmod 0000 /android-root/dev/.coldboot_done 2>/dev/null || true
log '[rgsp-android] inherited devtmpfs marked coldboot-ready'

if [ "$BOOT_MOUNTED" -eq 1 ]; then
  echo '[rgsp-android] executing Android init; subsequent stdout/stderr follows' >> /android-root/rgsp-persist/RGSP_ANDROID_BOOT_LAST.log
  sync
  exec /bin/busybox switch_root /android-root /init selinux_setup >> /android-root/rgsp-persist/RGSP_ANDROID_BOOT_LAST.log 2>&1
else
  exec /bin/busybox switch_root /android-root /init selinux_setup
fi
