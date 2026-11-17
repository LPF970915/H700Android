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

show_loading() {
    # Saved and one-time boots skip input completely. Repaint after the fresh
    # panel initialization so userdata preparation has a visible waiting frame.
    loading_tries=0
    while [ "$loading_tries" -lt 20 ] && [ ! -c /dev/fb0 ]; do
        loading_tries=$((loading_tries+1)); sleep 1
    done
    [ -c /dev/fb0 ] || { note 'loading framebuffer unavailable; continuing'; return 0; }
    if [ -w /sys/class/graphics/fb0/blank ]; then
        echo 0 > /sys/class/graphics/fb0/blank || true
    fi
    /grow/roc-boot-selector --loading-only --fb /dev/fb0 --rotation "$ROTATION" ||
        note 'loading frame unavailable; continuing'
}

# Always verify the integrated environment before using a saved/one-time route.
# Do not source or eval partition content. Preview readback is parsed as data.
mkdir -p /run
INITIAL_STATUS=/run/roc-selector-initial-state
PREVIEW_STATUS=/run/roc-selector-preview-state
[ ! -e "$INITIAL_STATUS" ] && [ ! -L "$INITIAL_STATUS" ] &&
    [ ! -e "$PREVIEW_STATUS" ] && [ ! -L "$PREVIEW_STATUS" ] || {
    stop 'unexpected prior state output'; exit 1;
}
/grow/roc-boot-state --partition "$ENV_DEV" status > "$INITIAL_STATUS" || exit 1
if [ "$ROUTE" != selector ]; then
    /grow/roc-boot-state --partition "$ENV_DEV" clear-next || exit 1
    show_loading
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
[ -d /dev/input ] || { stop 'input unavailable'; exit 1; }
# A failed framebuffer still permits volume trial. The native program refuses
# ordinary Start confirmation in that blind mode and never guesses a panel.
if [ -w /sys/class/graphics/fb0/blank ]; then
    echo 0 > /sys/class/graphics/fb0/blank || true
fi
retry_preview() {
    note 'trial update/result validation failed; returning to manual selection'
    # Native created RESULT exclusively in this fresh /run invocation, and
    # shell redirection created PARSED. Never remove a link or unknown output.
    [ -f "$RESULT" ] && [ ! -L "$RESULT" ] && [ -f "$PARSED" ] && [ ! -L "$PARSED" ] || {
        note 'ERROR: unsafe retry outputs; stopping'; while :; do sleep 60; done
    }
    rm -f "$RESULT" "$PARSED" || {
        note 'ERROR: could not remove trial outputs; stopping'; while :; do sleep 60; done
    }
}
while :; do
while :; do
    status=0
    selector_fb=1
    [ -c /dev/fb0 ] || selector_fb=0
    /grow/roc-boot-selector --fb /dev/fb0 --input-directory /dev/input \
        --output "$RESULT" --initial-model "$MODEL" \
        --rotation "$ROTATION" --available-models rg34xx,rg34xxsp,rgsp,rgcubexx,rg35xxplus,rg35xx_2025,rg28xx,rg35xxh,rg40xxh,rg40xxv,rg35xxsp,rg35xxpro --timeout 300 || status=$?
    case "$status" in
        0) [ "$selector_fb" = 1 ] || { stop 'blind confirmation refused'; exit 1; }; break;;
        4) break;;
        3) note 'waiting for manual choice';;
        *) stop "native selector failed ($status)"; exit 1;;
    esac
done
if ! /grow/roc-boot-state --result "$RESULT" > "$PARSED"; then
    if [ "$status" = 4 ]; then retry_preview; continue; fi
    exit 1
fi
read_result() {
CHOSEN=
SAVE=
while IFS= read -r row; do
    case "$row" in
        model=*) [ -z "$CHOSEN" ] || return 1; CHOSEN=${row#*=}; [ -n "$CHOSEN" ] || return 1;;
        save=*) [ -z "$SAVE" ] || return 1; SAVE=${row#*=}; [ -n "$SAVE" ] || return 1;;
        *) return 1;;
    esac
done < "$PARSED"
case "$CHOSEN" in rg34xx|rg34xxsp|rgsp|rgcubexx|rg35xxplus|rg35xx_2025|rg28xx|rg35xxh|rg40xxh|rg40xxv|rg35xxsp|rg35xxpro) ;;
    *) return 1;; esac
case "$SAVE" in 0|1) ;; *) return 1;; esac
}
if ! read_result; then
    if [ "$status" = 4 ]; then retry_preview; continue; fi
    stop 'invalid parsed result'; exit 1
fi
note "chosen=$CHOSEN save=$SAVE"
if [ "$status" = 4 ]; then
    if [ "$SAVE" != 0 ]; then retry_preview; continue; fi
    # Resolve adjacency from the initialized model's logical geometry, never
    # the mutable highlighted choice. Other electrical profiles stay available
    # through the normal twelve-model confirmation route.
    case "$MODEL" in
        rg34xx|rg34xxsp|rgsp) TRIAL_NEXT=rgcubexx; TRIAL_PREV=rg35xxh;;
        rgcubexx) TRIAL_NEXT=rg35xxh; TRIAL_PREV=rg34xxsp;;
        *) TRIAL_NEXT=rg34xxsp; TRIAL_PREV=rgcubexx;;
    esac
    if [ "$CHOSEN" != "$TRIAL_NEXT" ] && [ "$CHOSEN" != "$TRIAL_PREV" ]; then
        retry_preview; continue
    fi
    read_status() {
        STATUS_SAVED=; STATUS_NEXT=; STATUS_START=; seen_saved=0; seen_next=0; seen_start=0
        while IFS= read -r row; do
            case "$row" in
                saved=*) [ "$seen_saved" = 0 ] || return 1; seen_saved=1; STATUS_SAVED=${row#*=};;
                next=*) [ "$seen_next" = 0 ] || return 1; seen_next=1; STATUS_NEXT=${row#*=};;
                next_start=*) [ "$seen_start" = 0 ] || return 1; seen_start=1; STATUS_START=${row#*=};;
                *) return 1;;
            esac
        done < "$1"
        [ "$seen_saved:$seen_next:$seen_start" = 1:1:1 ]
    }
    if ! read_status "$INITIAL_STATUS"; then retry_preview; continue; fi
    INITIAL_SAVED=$STATUS_SAVED
    preview_ok=0
    if /grow/roc-boot-state --partition "$ENV_DEV" preview "$CHOSEN" &&
        /grow/roc-boot-state --partition "$ENV_DEV" status > "$PREVIEW_STATUS" &&
        read_status "$PREVIEW_STATUS" && [ "$STATUS_SAVED" = "$INITIAL_SAVED" ] &&
        [ "$STATUS_NEXT" = "$CHOSEN" ] && [ "$STATUS_START" = 2 ]; then
        preview_ok=1
    fi
    if [ "$preview_ok" = 0 ]; then
        retry_preview; continue
    fi
    note 'trial panel stored and verified; rebooting back to model menu'
    sync || {
        note 'ERROR: could not synchronize trial state; stopping'; while :; do sleep 60; done
    }
    /bin/busybox reboot -f || true
    note 'ERROR: preview reboot returned unexpectedly; stopping'
    while :; do sleep 60; done
fi
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
done
