#!/bin/bash
set -euo pipefail
source=/home/lpf/h700-android10/longan/kernel/linux-4.9
mount --bind "$source" "$source"
mount -o remount,bind,ro "$source"
exec /usr/sbin/runuser -u lpf -- /usr/bin/python3 -B \
  /mnt/d/Works/H700Android/tools/input_profiles/stick_build_v2/build.py
