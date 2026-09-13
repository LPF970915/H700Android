#!/bin/bash
# Isolated Ubuntu arm64 runtime; does not change host apt sources or packages.
set -euo pipefail
root=${1:?output directory}
mkdir -p "$root"/{lists/partial,cache/archives/partial,debs,runtime}
source_file="$(dirname "$(readlink -f "$0")")/rgsp_grow_runtime.sources"
opts=(-o "Dir::Etc::sourcelist=$source_file" -o Dir::Etc::sourceparts=-
      -o "Dir::State::lists=$root/lists" -o "Dir::Cache=$root/cache"
      -o APT::Architecture=arm64 -o APT::Architectures=arm64)
apt-get "${opts[@]}" update
cd "$root/debs"
apt-get "${opts[@]}" download fatresize dosfstools libparted2t64 libparted-fs-resize0t64 \
    libuuid1 libblkid1 libdevmapper1.02.1 libudev1 libselinux1 libpcre2-8-0 \
    libc6 libreadline8t64 libtinfo6 libcap2
sha256sum ./*.deb > "$root/packages.sha256"
for package in ./*.deb; do dpkg-deb -x "$package" "$root/runtime"; done
qemu-aarch64 "$root/runtime/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1" \
    --library-path "$root/runtime/usr/lib/aarch64-linux-gnu" \
    "$root/runtime/usr/sbin/fatresize" --help
