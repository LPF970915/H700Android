#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin

# The inherited devtmpfs bypasses ueventd coldboot during the Linux handoff.
for node in /dev/input/event*; do
    [ -c "$node" ] || continue
    chown root:input "$node"
    chmod 0660 "$node"
    restorecon "$node"
done
log -t RGSPInput "inherited evdev permissions restored; key calibration pending"
