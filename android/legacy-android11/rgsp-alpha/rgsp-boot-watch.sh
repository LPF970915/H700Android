#!/system/bin/sh

LOG=/rgsp-persist/RGSP_ANDROID_WATCH_LAST.log
STAGE=/rgsp-persist/RGSP_ANDROID_STAGE_LAST.log

exec >>"$LOG" 2>&1
echo "[rgsp-watch] started: $(date)"
echo "[rgsp-watch] cmdline: $(cat /proc/cmdline)"
rm -f /rgsp-persist/RGSP_ANDROID_LOGCAT_LAST.log
/system/bin/logcat -b all -v threadtime -f /rgsp-persist/RGSP_ANDROID_LOGCAT_LAST.log &

i=0
while [ "$i" -lt 60 ]; do
  echo "[rgsp-watch] sample=$i date=$(date)"
  echo "[rgsp-watch] stage=$(cat "$STAGE" 2>/dev/null)"
  echo "[rgsp-watch] pid1=$(tr '\000' ' ' < /proc/1/cmdline 2>/dev/null)"
  /system/bin/getprop 2>/dev/null | /system/bin/grep -E \
    '(^\[ro\.(boot|hardware)|^\[init\.svc\.(apexd|apexd-bootstrap|adbd|servicemanager|vold)|^\[sys\.(boot_completed|powerctl|usb)|^\[vold\.)' || true
  /system/bin/grep -E ' /(data|system|vendor|rgsp-persist) ' /proc/mounts 2>/dev/null || true
  if [ $((i % 6)) -eq 0 ]; then
    echo '[rgsp-watch] process snapshot'
    /system/bin/ps -A 2>/dev/null || true
    echo '[rgsp-watch] kernel tail'
    /system/bin/dmesg 2>/dev/null | /system/bin/tail -n 120 || true
  fi
  sync
  sleep 5
  i=$((i + 1))
done

echo '[rgsp-watch] five-minute watchdog expired; requesting normal Linux fallback reboot'
sync
/system/bin/setprop sys.powerctl reboot
sleep 15
echo 1 > /proc/sys/kernel/sysrq 2>/dev/null || true
echo b > /proc/sysrq-trigger 2>/dev/null || true
