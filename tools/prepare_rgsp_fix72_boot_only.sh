#!/bin/sh
# Run from original RGSP Linux. Default checks only; never reboots automatically.
set -eu

MODE=${1:---check}
[ "$#" -le 2 ] || exit 2
case "$MODE" in --check|--prepare) ;; *) echo 'Use --check or --prepare' >&2; exit 2 ;; esac
PROFILE=${2:-frozen}
case "$PROFILE" in frozen|codec|audio) ;; *) echo 'Use frozen, codec or audio profile' >&2; exit 2 ;; esac
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

B=/mnt/sdcard
LINUX_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ENV_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
BASE_SHA=6f65dd6571f80b07beb1329b058bb1f0b113c94f8d4f9f153fbd9f9274c2eb37
RAMDISK_SHA=8160e3a4f4f96a9b6985969003529263ce98a7719c6eb729b0a790a4bc16babd
BOOT_SHA=c3745e62bf2e965d7f798c7f2fa851ab43e67bcb463998156a9ccdcc59d06662
SYSTEM_SHA=199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa
VENDOR_SHA=cb65140203807d0d80408e314f0c76554f2f81cd13fc76bf8ef07a4e46243c34
CODEC_VENDOR_SHA=1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891
AUDIO_VENDOR_SHA=9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2
if [ "$PROFILE" = codec ]; then VENDOR_SHA=$CODEC_VENDOR_SHA; fi
if [ "$PROFILE" = audio ]; then VENDOR_SHA=$AUDIO_VENDOR_SHA; fi
WORK=
BOOT_DIRTY=0
PREPARED=0
sha() { sha256sum "$1" | awk '{print $1}'; }
env_sha() { dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}'; }
check_runtime_identity() {
    [ "$(id -u)" = 0 ]
    [ "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5 ]
    [ "$(findmnt -n -o SOURCE --target "$B")" = /dev/mmcblk1p1 ]
    [ "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7 ]
    [ "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b ]
    [ "$(cat /sys/class/power_supply/axp2202-usb/online)" = 1 ]
}
require_unmounted() {
    rc=0
    findmnt -rn -S "$1" >/dev/null || rc=$?
    [ "$rc" -eq 1 ] || { echo "Mounted or unknown mount state: $1" >&2; exit 1; }
}

require_clean_ext4_header() {
    # A read-only e2fsck can exit zero while journal recovery is pending.
    header=$(LC_ALL=C tune2fs -l "$1") || {
        echo "EXT4_HEADER_READ_FAILED: $1; no repair or boot preparation." >&2
        exit 1
    }
    if ! printf '%s\n' "$header" | LC_ALL=C awk '
        /^Filesystem features:/ {
            features++
            for (i=3; i<=NF; i++) if ($i == "needs_recovery") pending=1
        }
        /^Filesystem state:/ {
            states++
            if (NF != 3 || $3 != "clean") bad=1
        }
        END { exit(features!=1 || states!=1 || pending || bad) }
    '; then
        printf '%s\n' "$header" >&2
        echo "EXT4_RECOVERY_OR_STATE_REVIEW_REQUIRED: $1; no repair or boot preparation." >&2
        exit 1
    fi
}

require_clean_fsck() {
    rc=0
    diagnostics=$(LC_ALL=C e2fsck -fn "$1" 2>&1) || rc=$?
    printf '%s\n' "$diagnostics"
    if [ "$rc" -ne 0 ]; then
        echo "READONLY_FSCK_FAILED: $1 (exit $rc); boot preparation stopped." >&2
        echo 'No repair performed. Review the filesystem and journal against the verified backup.' >&2
        exit "$rc"
    fi
    if ! printf '%s\n' "$diagnostics" | LC_ALL=C awk '
        /^Pass [1-5]:/ { passes[substr($0,6,1)]++ }
        tolower($0) ~ /\?|warning|wrong|corrupt|error|recover|modified|invalid|abort/ { bad=1 }
        END {
            if (bad) exit 1
            for (i=1; i<=5; i++) if (passes[i]!=1) exit 1
            exit 0
        }
    '; then
        echo "READONLY_FSCK_DIAGNOSTICS_REVIEW_REQUIRED: $1; no repair or boot preparation." >&2
        exit 1
    fi
}

cleanup() {
    rc=$?
    trap - EXIT INT TERM
    if [ "$BOOT_DIRTY" -eq 1 ] && [ "$PREPARED" -eq 0 ]; then
        echo 'Preparation failed; restoring original Linux boot.' >&2
        if dd if="$B/rgsp-linux-boot-original.img" of=/dev/mmcblk0p4 bs=1M conv=fsync &&
           [ "$(sha /dev/mmcblk0p4)" = "$LINUX_SHA" ]; then
            rm -f "$B/RGSP_ANDROID_TRY.ONCE"
            sync
            echo 'LINUX_BOOT_ROLLBACK_OK' >&2
        else
            echo 'LINUX_BOOT_ROLLBACK_FAILED: do not reboot; retain UART for recovery.' >&2
        fi
        rc=1
    fi
    if [ -n "$WORK" ]; then
        rm -f "$WORK/boot.img"
        rmdir "$WORK"
    fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 1' INT TERM

check_runtime_identity
[ "$(blockdev --getsize64 /dev/mmcblk0p4)" = 67108864 ]
[ "$(sha /dev/mmcblk0p4)" = "$LINUX_SHA" ]
[ "$(sha "$B/rgsp-linux-boot-original.img")" = "$LINUX_SHA" ]
[ "$(env_sha)" = "$ENV_SHA" ]
[ ! -e "$B/RGSP_ANDROID_TRY.ONCE" ]
[ "$(sha "$B/h700-android10-b3-diag3-boot.img.gz9")" = "$BASE_SHA" ]
[ "$(sha "$B/ramdisk-a10-handoff-fix67.gz")" = "$RAMDISK_SHA" ]

for spec in \
    '1:268435456:0720745f-bbfb-4940-bef7-8595c6f34f4b' \
    '2:8589934592:096d7fa1-62e8-c242-9876-cfdd5a92b8eb' \
    '3:2147483648:6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8' \
    '4:17179869184:734716ed-e7d9-e74f-9b3e-4f1cb8d448ed' \
    '5:96883162624:324a1514-de37-6344-8d09-ed5dd8b90da2'; do
    part=${spec%%:*}
    rest=${spec#*:}
    dev=/dev/mmcblk1p$part
    [ "$(blockdev --getsize64 "$dev")" = "${rest%%:*}" ]
    [ "$(blkid -s PARTUUID -o value "$dev")" = "${rest#*:}" ]
done
for p in /dev/mmcblk1p2 /dev/mmcblk1p3 /dev/mmcblk1p4; do
    require_unmounted "$p"
    require_clean_ext4_header "$p"
    require_clean_fsck "$p"
done
echo 'Checking complete system/vendor hashes; keep power connected.'
[ "$(sha /dev/mmcblk1p2)" = "$SYSTEM_SHA" ]
[ "$(sha /dev/mmcblk1p3)" = "$VENDOR_SHA" ]

WORK=$(mktemp -d /run/rgsp-fix72-boot.XXXXXX)
gzip -dc "$B/h700-android10-b3-diag3-boot.img.gz9" > "$WORK/boot.img"
python3 - "$WORK/boot.img" "$B/ramdisk-a10-handoff-fix67.gz" <<'PY'
import pathlib, struct, sys
boot = pathlib.Path(sys.argv[1])
ramdisk = pathlib.Path(sys.argv[2]).read_bytes()
if boot.stat().st_size != 67108864 or len(ramdisk) != 2605108:
    raise ValueError("Pinned boot/ramdisk size mismatch")
with boot.open("r+b") as f:
    header = f.read(2048)
    if header[:8] != b"ANDROID!" or struct.unpack_from("<I", header, 36)[0] != 2048:
        raise ValueError("Unexpected legacy boot header")
    kernel_size = struct.unpack_from("<I", header, 8)[0]
    offset = 2048 + ((kernel_size + 2047) // 2048) * 2048
    if offset != 8638 * 2048 or offset + len(ramdisk) >= boot.stat().st_size:
        raise ValueError("Unexpected ramdisk offset")
    f.seek(offset)
    f.write(ramdisk)
    f.seek(16)
    f.write(struct.pack("<I", len(ramdisk)))
    f.seek(64)
    f.write(b"selinux=1 enforcing=0 androidboot.selinux=permissive".ljust(512, b"\0"))
PY
[ "$(sha "$WORK/boot.img")" = "$BOOT_SHA" ]
echo "FIX72_BOOT_PROFILE=$PROFILE VENDOR_SHA=$VENDOR_SHA"
echo 'FIX72_BOOT_ONLY_CHECK_OK'
if [ "$MODE" = --check ]; then
    exit 0
fi

check_runtime_identity
for p in /dev/mmcblk1p2 /dev/mmcblk1p3 /dev/mmcblk1p4; do
    require_unmounted "$p"
    require_clean_ext4_header "$p"
done
[ "$(sha /dev/mmcblk0p4)" = "$LINUX_SHA" ]
[ "$(sha "$B/rgsp-linux-boot-original.img")" = "$LINUX_SHA" ]
[ "$(env_sha)" = "$ENV_SHA" ]
[ ! -e "$B/RGSP_ANDROID_TRY.ONCE" ]

# This is the existing one-shot TF1 boot replacement, not independent TF2 boot.
# Mark dirty before writing so a partial write also triggers Linux restoration.
BOOT_DIRTY=1
dd if="$WORK/boot.img" of=/dev/mmcblk0p4 bs=1M conv=fsync
[ "$(sha /dev/mmcblk0p4)" = "$BOOT_SHA" ]
printf 'A10-FIX72-BOOT-ONLY boot=%s\n' "$BOOT_SHA" > "$B/RGSP_ANDROID_TRY.ONCE"
sync
[ "$(env_sha)" = "$ENV_SHA" ]
PREPARED=1
echo 'FIX72_BOOT_ONLY_PREPARED: system/vendor/data untouched; reboot separately.'
