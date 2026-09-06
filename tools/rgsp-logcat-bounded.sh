#!/system/bin/sh
LOG=/rgsp-persist/RGSP_ANDROID_LOGCAT_BOUNDED.log
DIAG=/rgsp-persist/RGSP_ANDROID_FIX47_EGL_DIAG_LAST.log
echo "[fix64-logcat] bounded capture started: $(date)" >> "$DIAG"
exec /system/bin/logcat -b all -v threadtime -T 5000 \
    -f "$LOG" -r 4096 -n 3 2>> "$DIAG"
