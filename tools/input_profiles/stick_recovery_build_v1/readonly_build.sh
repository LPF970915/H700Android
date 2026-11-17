#!/bin/bash
set -euo pipefail
repo=$1
mount --bind /home/lpf/h700-android10/longan/kernel/linux-4.9 /home/lpf/h700-android10/longan/kernel/linux-4.9
mount -o remount,bind,ro /home/lpf/h700-android10/longan/kernel/linux-4.9
exec /usr/sbin/runuser -u lpf -- /usr/bin/python3 -B "$repo/tools/input_profiles/stick_recovery_build_v1/build.py"
