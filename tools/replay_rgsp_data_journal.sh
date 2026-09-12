#!/bin/sh
# Original RGSP preimage check only. Replay is disabled after the scope incident.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL=C
MODE=${1:---check}
[ "$#" -le 1 ] || exit 2
case "$MODE" in
    --check) ;;
    --replay)
        echo 'REPLAY_DISABLED: the earlier journal_only -fy command exceeded journal-only scope.' >&2
        echo 'Only --check is available; no device repair will be attempted.' >&2
        exit 3
        ;;
    *) echo 'Use --check; replay is disabled' >&2; exit 2 ;;
esac

DATA=/dev/mmcblk1p4
BEFORE_SHA=2d024b9cb43c42c4c86d9de50fe22314de18ae1f366015301dcbc1c5656a32b5
LINUX_SHA=d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
ENV_SHA=d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
sha() { sha256sum "$1" | awk '{print $1}'; }
env_sha() { dd if=/dev/mmcblk0p3 bs=128K count=1 status=none | sha256sum | awk '{print $1}'; }
identity() {
    [ "$(id -u)" = 0 ]
    [ "$(findmnt -n -o SOURCE /)" = /dev/mmcblk0p5 ]
    [ "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7 ]
    [ "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b ]
    [ "$(blockdev --getsize64 "$DATA")" = 17179869184 ]
    [ "$(blkid -s PARTUUID -o value "$DATA")" = 734716ed-e7d9-e74f-9b3e-4f1cb8d448ed ]
    [ "$(blkid -s UUID -o value "$DATA")" = 45daaa6e-724e-4d20-981c-602b3f72b8a2 ]
    [ "$(blkid -s TYPE -o value "$DATA")" = ext4 ]
    [ "$(cat /sys/class/power_supply/axp2202-usb/online)" = 1 ]
    rc=0
    findmnt -rn -S "$DATA" >/dev/null || rc=$?
    [ "$rc" -eq 1 ] || { echo 'DATA_MOUNT_CHECK_FAILED' >&2; exit 1; }
}
identity
[ "$(sha /dev/mmcblk0p4)" = "$LINUX_SHA" ]
[ "$(env_sha)" = "$ENV_SHA" ]
echo 'DATA_PREIMAGE_HASH_BEGIN: verifying all 16 GiB against the original host backup.'
[ "$(sha "$DATA")" = "$BEFORE_SHA" ]
echo "DATA_PREIMAGE_HASH_OK=$BEFORE_SHA"
echo 'DATA_JOURNAL_CHECK_OK: no replay performed.'
