#!/system/bin/sh
# Explicit, temporary debug session. Run from UART after boot; no persistent port.
set -eu
export PATH=/system/bin:/vendor/bin
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = 5c001089d750c872012 ]
[ "$(getprop sys.boot_completed)" = 1 ]
setprop service.adb.tcp.port -1
stop adbd
iptables -C INPUT -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP 2>/dev/null ||
    iptables -I INPUT 1 -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP
ip6tables -C INPUT -p tcp --dport 5555 -j DROP 2>/dev/null ||
    ip6tables -I INPUT 1 -p tcp --dport 5555 -j DROP
setprop service.adb.tcp.port 5555
start adbd
echo DEBUG_GUARDS_RESTORED
ip -4 addr show wlan0 | grep 'inet ' || true
