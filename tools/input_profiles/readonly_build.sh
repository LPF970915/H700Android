#!/bin/bash
set -euo pipefail
repo=${1:?repository}
work=${2:?new isolated work}
output=${3:?new output}
source=/home/lpf/h700-android10/longan/kernel/linux-4.9
test "$(id -u)" = 0
# This script is entered only in a fresh private mount namespace. The bind
# protects original BSP sources even if an old kernel make rule writes there.
mount --bind "$source" "$source"
mount -o remount,bind,ro "$source"
exec /usr/sbin/runuser -u lpf -- /usr/bin/python3 -B \
    "$repo/tools/input_profiles/build_module.py" --work "$work" --output "$output" --execute
