#!/system/bin/sh
# Capture a short, timestamped input sample for H700 key mapping.
# Run from adb shell; output is safe to pull into the project afterwards.
OUT=${1:-/data/local/tmp/rgsp-input-events.txt}
echo "# $(date)" > "$OUT"
echo "# devices" >> "$OUT"
getevent -lp >> "$OUT" 2>&1
echo "# events (press each physical key once)" >> "$OUT"
if command -v timeout >/dev/null 2>&1; then
    timeout 30 getevent -t >> "$OUT" 2>&1
else
    # Minimal Android shells may not ship timeout; collect until Ctrl-C.
    getevent -t >> "$OUT" 2>&1
fi
echo "$OUT"
