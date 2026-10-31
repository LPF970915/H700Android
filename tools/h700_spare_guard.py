"""Generate exact CID guards; MMC minors are discovered per kernel boot."""
import re
import shlex
from dualabi_image_layout import STARTS,LENGTHS

def spare_guard(serial, original_cid, spare_cid, partitions=(5,6)):
    if not all(re.fullmatch('[a-fA-F0-9]{32}',v) for v in [original_cid,spare_cid]):raise ValueError('Invalid private CID')
    if not partitions or any(p not in (5,6,7) for p in partitions):raise ValueError('Unexpected target partition')
    text=f'''set -eu
export PATH=/system/bin:/vendor/bin
[ "$(getprop ro.serialno)" = {shlex.quote(serial)} ]
[ "$(getprop ro.product.device)" = rgsp ]
[ "$(getprop persist.vendor.rgsp.input_profile)" = rg34xxsp ]
[ -z "$(getprop ro.h700.prototype)" ]
[ "$(id -u)" = 0 ]
[ "$(cat /sys/block/mmcblk0/device/cid)" = {original_cid} ]
[ "$(cat /sys/block/mmcblk1/device/cid)" = {spare_cid} ]
[ "$(cat /sys/block/mmcblk1/size)" = 244277248 ]
grep -q '^/dev/mmcblk0p5 / ' /proc/mounts
grep -q '^/dev/mmcblk0p6 /vendor ' /proc/mounts
grep -q '^/dev/mmcblk0p7 /data ' /proc/mounts
! grep -q mmcblk1 /proc/mounts
! grep -q mmcblk1 /proc/swaps
[ "$(cat /sys/block/mmcblk0/dev)" != "$(cat /sys/block/mmcblk1/dev)" ]
for f in /sys/block/mmcblk1/dev /sys/block/mmcblk1/mmcblk1p*/dev; do
 number=$(cat "$f")
 awk -v d="$number" '$3==d {{bad=1}} END {{exit bad}}' /proc/self/mountinfo
done
for d in /sys/block/mmcblk1 /sys/block/mmcblk1/mmcblk1p*; do
 [ -d "$d/holders" ]
 [ -z "$(ls -A "$d/holders")" ]
done
'''
    for p in partitions:
        text+=f'''[ -b /dev/block/mmcblk1p{p} ]
[ "$(cat /sys/block/mmcblk1/mmcblk1p{p}/start)" = {STARTS[p-1]//512} ]
[ "$(cat /sys/block/mmcblk1/mmcblk1p{p}/size)" = {LENGTHS[p-1]//512} ]
number=$(cat /sys/block/mmcblk1/mmcblk1p{p}/dev)
major=${{number%:*}}; minor=${{number#*:}}
[ "$(stat -c %t:%T /dev/block/mmcblk1p{p})" = "$(printf '%x:%x' "$major" "$minor")" ]
'''
    return text+'echo EXACT_SPARE_PARTITIONS_UNMOUNTED\n'
