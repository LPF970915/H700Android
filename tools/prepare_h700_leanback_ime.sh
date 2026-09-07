#!/bin/bash
set -euo pipefail

root=$(realpath "${1:?Usage: prepare_h700_leanback_ime.sh ANDROID_SOURCE_ROOT}")
tools=$(cd "$(dirname "$0")" && pwd)
test -f "$root/build/envsetup.sh"
target="$root/packages/inputmethods/LeanbackIME"
revision=1667592ee5924122e43b611fa813c8f894087cd6
origin=https://android.googlesource.com/platform/packages/inputmethods/LeanbackIME

if [ ! -e "$target" ]; then
    git clone --depth 1 --branch android11-release "$origin" "$target"
fi
test "$(git -C "$target" rev-parse --show-toplevel)" = "$target"
test "$(git -C "$target" rev-parse HEAD)" = "$revision"
test "$(git -C "$target" config --get remote.origin.url)" = "$origin"
patch="$tools/h700-leanback-ime-rgsp.patch"
if git -C "$target" apply --reverse --check "$patch" 2>/dev/null; then
    git -C "$target" diff --binary | cmp - "$patch"
    test -z "$(git -C "$target" ls-files --others --exclude-standard)"
    echo LEANBACK_RGSP_PATCH_ALREADY_PRESENT
else
    test -z "$(git -C "$target" status --porcelain)"
    git -C "$target" apply --check "$patch"
    git -C "$target" apply "$patch"
    echo LEANBACK_RGSP_PATCH_APPLIED
fi
echo "SOURCE_REVISION=$revision"
echo 'Build with the Android 10 h700_rgsp-eng environment: m -j4 LeanbackIME'
