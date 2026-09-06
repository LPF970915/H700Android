#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin

LOG=/rgsp-persist/RGSP_ANDROID_KMSG_BOUNDED.log
/vendor/bin/rgsp_kmsg_logger "$LOG" &
reader=$!
trap 'kill "$reader" 2>/dev/null || true; wait "$reader" 2>/dev/null || true' EXIT
trap 'exit 0' TERM INT
sleep 1
kill -0 "$reader"
[ -s "$LOG" ]

# Stop only the inherited reader of the historical handoff log, after the
# bounded replacement is alive. Do not truncate or delete the old evidence.
for process in /proc/[0-9]*; do
    command=$(tr '\000' ' ' 2>/dev/null < "$process/cmdline") || continue
    case "$command" in
        "busybox cat /dev/kmsg "|"/bin/busybox cat /dev/kmsg ") ;;
        *) continue ;;
    esac
    target=$(readlink "$process/fd/1" 2>/dev/null) || continue
    [ "$target" = /rgsp-boot/RGSP_ANDROID_KMSG_LAST.log ] || continue
    kill "${process##*/}"
done
wait "$reader"
