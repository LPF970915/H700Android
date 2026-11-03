#!/bin/sh
# Before any TF1 partition is mounted. Never formats or migrates a card.
set -eu
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
disk=${1:?TF1 device required}
data=${disk}p7
helper=/grow/roc-grow-userdata-gpt
rc=0
"$helper" --check "$disk" || rc=$?
case "$rc" in
    0) ;;
    4)
        rc=0
        "$helper" --apply "$disk" || rc=$?
        case "$rc" in
            0) ;;
            4) sync; reboot -f; exit 1 ;;
            *) exit "$rc" ;;
        esac
        ;;
    *) exit "$rc" ;;
esac
rc=0
"$helper" --check-volume "$data" || rc=$?
case "$rc" in 0) exit 0 ;; 4) ;; *) exit "$rc" ;; esac
rc=0
/grow/e2fsck_static -f -p "$data" || rc=$?
case "$rc" in 0|1) ;; *) exit "$rc" ;; esac
/grow/roc-resize2fs-static "$data"
"$helper" --check-volume "$data"
sync
