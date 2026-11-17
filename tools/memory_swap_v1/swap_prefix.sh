# Common pre-Android resource setup. This prefix runs before every model's
# optional stick handling, including models with no sticks. A swap failure
# must never prevent the original input helper or Android from starting.
h700_swap_setup() (
    set -u
    set -f
    umask 077
    [ "$#" -ge 4 ] && [ "$#" -le 6 ] || return 1
    swap_root=$1
    swap_box=$3
    swap_data="$swap_root/data"
    swap_dir="$swap_data/roc-swap"
    swap_file="$swap_dir/swapfile-2g"
    swap_stage="$swap_dir/swapfile-2g.new"
    swap_proc=/proc/swaps
    swap_mounts=/proc/mounts
    swap_bytes=2147483648
    swap_usable_kib=2097148
    swap_last_page=524287
    swap_blocks=2048
    swap_required_kib=2621440
    swap_timeout=300
    swap_owner='0 0'
    case "$swap_root" in /*) ;; *) return 1 ;; esac
    [ -d "$swap_root" ] && [ ! -L "$swap_root" ] || return 1
    [ -d "$swap_data" ] && [ ! -L "$swap_data" ] || return 1
    [ -x "$swap_box" ] && [ -r "$swap_proc" ] && [ -r "$swap_mounts" ] || return 1
    # Only the already mounted TF1 ext4 userdata is eligible; never TF2,
    # a block partition, a sparse allocation, or a different filesystem.
    "$swap_box" awk -v path="$swap_data" \
        '$2 == path && $3 == "ext4" && $4 ~ /(^|,)rw(,|$)/ {ok=1} END {exit !ok}' \
        "$swap_mounts" || return 1
    if [ -e "$swap_dir" ] || [ -L "$swap_dir" ]; then
        [ -d "$swap_dir" ] && [ ! -L "$swap_dir" ] || return 1
    else
        "$swap_box" mkdir -m 0700 "$swap_dir" || return 1
    fi
    swap_meta=$("$swap_box" ls -ldn "$swap_dir" 2>/dev/null | \
        "$swap_box" awk '{print $1 " " $3 " " $4}')
    [ "$swap_meta" = "drwx------ $swap_owner" ] || return 1
    if [ -e "$swap_file" ] || [ -L "$swap_file" ]; then
        [ -f "$swap_file" ] && [ ! -L "$swap_file" ] || return 1
        swap_meta=$("$swap_box" ls -ldn "$swap_file" 2>/dev/null | \
            "$swap_box" awk '{print $1 " " $2 " " $3 " " $4 " " $5}')
        [ "$swap_meta" = "-rw------- 1 $swap_owner $swap_bytes" ] || return 1
        if "$swap_box" awk -v first="$swap_file" -v second=/data/roc-swap/swapfile-2g \
            '$1 == first || $1 == second {ok=1} END {exit !ok}' "$swap_proc"; then
            "$swap_box" awk -v first="$swap_file" -v second=/data/roc-swap/swapfile-2g -v size="$swap_usable_kib" \
                '($1 == first || $1 == second) && $2 == "file" && $3 == size {ok=1} END {exit !ok}' \
                "$swap_proc" || return 1
            echo '[h700-swap] 2GiB swap already active; preserving it'
            return 0
        fi
        swap_magic=$("$swap_box" dd if="$swap_file" bs=1 skip=4086 count=10 2>/dev/null)
        [ "$swap_magic" = SWAPSPACE2 ] || return 1
        echo '[h700-swap] reusing existing 2GiB swap file'
    else
        # Remove only a single-link private staging file left by our own
        # interrupted creation. Unknown files and links remain untouched.
        if [ -e "$swap_stage" ] || [ -L "$swap_stage" ]; then
            [ -f "$swap_stage" ] && [ ! -L "$swap_stage" ] || return 1
            if "$swap_box" awk -v first="$swap_stage" -v second=/data/roc-swap/swapfile-2g.new \
                '$1 == first || $1 == second {ok=1} END {exit !ok}' "$swap_proc"; then
                echo '[h700-swap] staging file is active swap; preserving it'
                return 1
            fi
            swap_meta=$("$swap_box" ls -ldn "$swap_stage" 2>/dev/null | \
                "$swap_box" awk '{print $1 " " $2 " " $3 " " $4}')
            [ "$swap_meta" = "-rw------- 1 $swap_owner" ] || return 1
            "$swap_box" rm -f "$swap_stage" || return 1
        fi
        swap_free=$("$swap_box" df -Pk "$swap_data" 2>/dev/null | \
            "$swap_box" awk 'NR>1 {free=$4} END {print free}')
        case "$swap_free" in ''|*[!0-9]*) return 1 ;; esac
        [ "$swap_free" -ge "$swap_required_kib" ] || return 1
        echo '[h700-swap] preparing 2GiB TF1 swap; first boot may take several minutes'
        # Full sequential writes plus fsync allocate every page. Do not use
        # fallocate, truncate, seek, or a header-only sparse production file.
        "$swap_box" dd if=/dev/zero of="$swap_stage" bs=1048576 \
            count="$swap_blocks" conv=fsync &
        swap_pid=$!
        swap_waited=0
        while "$swap_box" kill -0 "$swap_pid" 2>/dev/null; do
            if [ "$swap_waited" -ge "$swap_timeout" ]; then
                "$swap_box" kill -KILL "$swap_pid" 2>/dev/null || true
                if ! "$swap_box" kill -0 "$swap_pid" 2>/dev/null; then
                    wait "$swap_pid" 2>/dev/null || true
                fi
                echo '[h700-swap] creation timed out; continuing without swap'
                return 1
            fi
            "$swap_box" sleep 1
            swap_waited=$((swap_waited + 1))
        done
        wait "$swap_pid" || return 1
        swap_meta=$("$swap_box" ls -ldn "$swap_stage" 2>/dev/null | \
            "$swap_box" awk '{print $1 " " $2 " " $3 " " $4 " " $5}')
        [ "$swap_meta" = "-rw------- 1 $swap_owner $swap_bytes" ] || return 1
        "$swap_box" mkswap "$swap_stage" || return 1
        swap_magic=$("$swap_box" dd if="$swap_stage" bs=1 skip=4086 count=10 2>/dev/null)
        [ "$swap_magic" = SWAPSPACE2 ] || return 1
        "$swap_box" sync || return 1
        "$swap_box" mv "$swap_stage" "$swap_file" || return 1
        "$swap_box" sync || return 1
    fi
    "$swap_box" od -An -tu4 -j1024 -N8 "$swap_file" | \
        "$swap_box" awk -v last="$swap_last_page" \
        'NF == 2 && $1 == 1 && $2 == last {ok=1} END {exit !ok}' || return 1
    # The existing kernel provides swap support. This call runs before the
    # Android policy handoff; no root/SELinux change or Android service needed.
    "$swap_box" swapon "$swap_file" || return 1
    "$swap_box" awk -v first="$swap_file" -v second=/data/roc-swap/swapfile-2g -v size="$swap_usable_kib" \
        '($1 == first || $1 == second) && $2 == "file" && $3 == size {ok=1} END {exit !ok}' "$swap_proc" || return 1
    echo '[h700-swap] 2GiB TF1 swap enabled'
    return 0
)
if ! h700_swap_setup "$@"; then
    echo '[h700-swap] optional 2GiB swap unavailable; continuing normal startup'
fi

