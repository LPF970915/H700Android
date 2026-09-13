#!/bin/bash
set -euo pipefail
tools=$(dirname "$(readlink -f "$0")")
build=${1:-/home/lpf/rgsp-grow-build}
runtime=${2:-/home/lpf/rgsp-grow-runtime/runtime}
mkdir -p "$build"
gcc -Wall -Wextra -Werror -O2 "$tools/rgsp_grow_gpt.c" -o "$build/grow-host"
aarch64-linux-gnu-gcc -Wall -Wextra -Werror -O2 -static \
    "$tools/rgsp_grow_gpt.c" -o "$build/rgsp-grow-gpt"
aarch64-linux-gnu-gcc -Wall -Wextra -Werror -O2 -idirafter /usr/include \
    "$tools/rgsp_grow_fat.c" -Wl,-rpath-link,"$runtime/usr/lib/aarch64-linux-gnu" \
    "$runtime/usr/lib/aarch64-linux-gnu/libparted-fs-resize.so.0" \
    "$runtime/usr/lib/aarch64-linux-gnu/libparted.so.2" -o "$build/rgsp-grow-fat"
qemu-aarch64 "$runtime/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1" \
    --library-path "$runtime/usr/lib/aarch64-linux-gnu" --list "$build/rgsp-grow-fat"
sha256sum "$build/rgsp-grow-gpt" "$build/rgsp-grow-fat"
