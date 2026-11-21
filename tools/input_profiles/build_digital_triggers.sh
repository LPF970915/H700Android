#!/bin/bash
set -euo pipefail

repo=$1
stage=$2
native=/home/lpf/h700-android10/android
cache=/home/lpf/roc-os-user-20261104/out
relative=frameworks/native/services/inputflinger/InputReader.cpp
source=$repo/build-support/public/overlay/$relative
product=$cache/target/product/roc_os_source64/system
targets=(lib/libinputreader.so lib64/libinputreader.so)

lock=/tmp/h700-android10-low-pressure.lock
if [[ ! -e "$lock" ]]; then
    runuser -u lpf -- touch "$lock"
fi
exec 9<"$lock"
flock -n 9
mount --make-rprivate /
printf '%s  %s\n' 54d30315220337fa3516b515aaffda8d5eb990ea8072a2171ebe34c03f00df58 \
    "$native/$relative" | sha256sum -c

mkdir "$stage"
mkdir "$stage"/{cache-lower,cache-upper,cache-work,built,bin}
chown lpf:lpf "$stage"/{cache-upper,built}
cp "$source" "$stage/InputReader.cpp"
ln -s /usr/bin/python3 "$stage/bin/python"
mount --bind "$cache" "$stage/cache-lower"
mount -o remount,bind,ro "$stage/cache-lower"
mount -t overlay overlay -o "lowerdir=$stage/cache-lower,upperdir=$stage/cache-upper,workdir=$stage/cache-work" "$cache"
mount --bind "$native" "$native"
mount -o remount,bind,ro "$native"
mount --bind "$stage/InputReader.cpp" "$native/$relative"
mount -o remount,bind,ro "$native/$relative"

for target in "${targets[@]}"; do
    cmp "$product/$target" "/home/lpf/roc-h700-chinese-ime-20261118-v4/candidate-system/system/$target"
done

cd "$native"
ninja="$native/prebuilts/build-tools/linux-x86/bin/ninja"
graph="$cache/combined-roc_os_release_candidate.ninja"
request=("$product/${targets[0]}" "$product/${targets[1]}")
export OUT_DIR="$cache" OMP_NUM_THREADS=1 GOMAXPROCS=1 MAKEFLAGS=-j1
export PATH="$stage/bin:$PATH"
export LD_LIBRARY_PATH=/home/lpf/roc-os-source64-20261103/host-compat/lib
runuser -u lpf --preserve-environment -- "$ninja" -f "$graph" -j1 -n "${request[@]}" | tee "$stage/ninja-plan.log"
count=$(grep -cE '^\[[0-9]+/[0-9]+\]' "$stage/ninja-plan.log" || true)
if ((count < 2 || count > 20)); then
    echo "Unexpected number of build actions: $count" >&2
    exit 1
fi
runuser -u lpf --preserve-environment -- "$ninja" -f "$graph" -j1 "${request[@]}"
for target in "${targets[@]}"; do
    if cmp -s "$product/$target" "$stage/cache-lower/target/product/roc_os_source64/system/$target"; then
        echo "Input reader did not change: $target" >&2
        exit 1
    fi
    install -D -m 0644 "$product/$target" "$stage/built/$target"
done
sha256sum "$stage/InputReader.cpp" "$stage/built/"lib*/libinputreader.so
