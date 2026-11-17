#!/bin/bash
# Root only for private read-only mounts; all build work runs as lpf.
set -euo pipefail
test "$EUID" = 0
test "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)"
repo=/mnt/d/Works/H700Android
native=/home/lpf/h700-android10/android
work=/home/lpf/roc-os-navigation-test6-build-20261115-v1
exec 9>/tmp/h700-android10-low-pressure.lock
flock -n 9
mount --make-rprivate /
runuser -u lpf -- python3 -B "$repo/tools/release/build_navigation_test6.py" prepare
mount --bind "$native" "$native"
mount -o remount,bind,ro "$native"
mount --bind "$work/source/ViewRootImpl.java" "$native/frameworks/base/core/java/android/view/ViewRootImpl.java"
mount -o remount,bind,ro "$native/frameworks/base/core/java/android/view/ViewRootImpl.java"
mount --bind "$work/source/Navigation" "$native/device/roc/roc_os_source64/Navigation"
mount -o remount,bind,ro "$native/device/roc/roc_os_source64/Navigation"
runuser -u lpf -- python3 -B "$repo/tools/release/build_navigation_test6.py" build
