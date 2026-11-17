#!/bin/sh
# Called by the original TF1-discovering init, before expansion or Android.
# Only the caller's already resolved sdc0 card may supply the env partition.
set -eu
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

note() { echo "[roc-selector] $*"; }
stop() { note "ERROR: $*"; return 1; }
[ "$#" -eq 1 ] || { stop 'missing TF1'; exit 1; }
case "$1" in /dev/mmcblk[0-9]|/dev/mmcblk[0-9][0-9]) ;; *) stop 'invalid TF1'; exit 1;; esac
TF1=$1
case "$(readlink -f "/sys/class/block/${TF1##*/}")" in
    */sdc0/mmc_host/*/block/mmcblk*) ;;
    *) stop 'TF1 controller mismatch'; exit 1;;
esac
ENV_DEV=${TF1}p3
[ -b "$ENV_DEV" ] || { stop 'environment partition unavailable'; exit 1; }

MODEL=
ROUTE=
LID=
for token in $(cat /proc/cmdline); do
    case "$token" in
        androidboot.roc_model=*)
            [ -z "$MODEL" ] || { stop 'duplicate model'; exit 1; }
            MODEL=${token#*=}; [ -n "$MODEL" ] || { stop 'empty model'; exit 1; };;
        androidboot.roc_route=*)
            [ -z "$ROUTE" ] || { stop 'duplicate route'; exit 1; }
            ROUTE=${token#*=}; [ -n "$ROUTE" ] || { stop 'empty route'; exit 1; };;
        androidboot.roc_clamshell=*)
            [ -z "$LID" ] || { stop 'duplicate lid flag'; exit 1; }
            LID=${token#*=}; [ -n "$LID" ] || { stop 'empty lid flag'; exit 1; };;
    esac
done
case "$MODEL:$LID" in rg34xx:0|rg34xxsp:1|rgsp:1|rgcubexx:0|rg35xxplus:0|rg35xx_2025:0|rg28xx:0|rg35xxh:0|rg40xxh:0|rg40xxv:0|rg35xxsp:1|rg35xxpro:0) ;;
    *) stop 'unsupported or inconsistent active model'; exit 1;; esac
case "$ROUTE" in selector|start_once|start_saved) ;; *) stop 'invalid boot route'; exit 1;; esac
ROTATION=0
[ "$MODEL" != rg28xx ] || ROTATION=90
note "active=$MODEL route=$ROUTE clamshell=$LID rotation=$ROTATION"

# Always verify the integrated environment before using a saved/one-time route.
# Do not source or eval partition content.
/grow/roc-boot-state --partition "$ENV_DEV" status || exit 1
if [ "$ROUTE" != selector ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" clear-next || exit 1
    note 'validated saved/one-time route; continuing to Android'
    exit 0
fi

mkdir -p /run
RESULT=/run/roc-selector-result.json
PARSED=/run/roc-selector-result.fields
[ ! -e "$RESULT" ] && [ ! -L "$RESULT" ] && [ ! -e "$PARSED" ] && [ ! -L "$PARSED" ] || {
    stop 'unexpected prior selector output'; exit 1;
}
tries=0
while [ "$tries" -lt 20 ]; do
    [ -c /dev/fb0 ] && [ -d /dev/input ] && break
    tries=$((tries+1)); sleep 1
done
[ -c /dev/fb0 ] && [ -d /dev/input ] || { stop 'display/input unavailable'; exit 1; }
if [ -w /sys/class/graphics/fb0/blank ]; then
    echo 0 > /sys/class/graphics/fb0/blank || true
fi
while :; do
    status=0
    /grow/roc-boot-selector --fb /dev/fb0 --input-directory /dev/input \
        --output "$RESULT" --initial-model "$MODEL" \
        --rotation "$ROTATION" --available-models rg34xx,rg34xxsp,rgsp,rgcubexx,rg35xxplus,rg35xx_2025,rg28xx,rg35xxh,rg40xxh,rg40xxv,rg35xxsp,rg35xxpro --timeout 300 || status=$?
    case "$status" in
        0) break;;
        3) note 'waiting for manual choice';;
        *) stop "native selector failed ($status)"; exit 1;;
    esac
done
/grow/roc-boot-state --result "$RESULT" > "$PARSED" || exit 1
CHOSEN=
SAVE=
while IFS= read -r row; do
    case "$row" in
        model=*) [ -z "$CHOSEN" ] || exit 1; CHOSEN=${row#*=}; [ -n "$CHOSEN" ] || exit 1;;
        save=*) [ -z "$SAVE" ] || exit 1; SAVE=${row#*=}; [ -n "$SAVE" ] || exit 1;;
        *) stop 'invalid parsed result'; exit 1;;
    esac
done < "$PARSED"
case "$CHOSEN" in rg34xx|rg34xxsp|rgsp|rgcubexx|rg35xxplus|rg35xx_2025|rg28xx|rg35xxh|rg40xxh|rg40xxv|rg35xxsp|rg35xxpro) ;;
    *) stop 'selected profile not integrated'; exit 1;; esac
case "$SAVE" in 0|1) ;; *) stop 'invalid save flag'; exit 1;; esac
note "chosen=$CHOSEN save=$SAVE"
if [ "$SAVE" = 1 ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" save "$CHOSEN" || exit 1
elif [ "$CHOSEN" != "$MODEL" ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" once "$CHOSEN" || exit 1
else
    # VolumeDown can reopen a pending one-time selection. Consume it even when
    # the user confirms this same model without changing the saved default.
    /grow/roc-boot-state --partition "$ENV_DEV" clear-next || exit 1
fi
if [ "$CHOSEN" = "$MODEL" ]; then
    note 'selection matches initialized hardware; continuing to Android'
    exit 0
fi
note 'selection stored and read back; rebooting to initialize selected panel'
sync
# No Android process or mounted Android filesystem exists at this point.
/bin/busybox reboot -f
stop 'reboot returned unexpectedly'
exit 1
