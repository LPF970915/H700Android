#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT="$ROOT/out/rgsp-logdw-capture"

aarch64-linux-gnu-gcc -O2 -Wall -Wextra -Werror -static \
  -o "$OUTPUT" "$ROOT/tools/rgsp_logdw_capture.c"
aarch64-linux-gnu-strip "$OUTPUT"
file "$OUTPUT"
sha256sum "$OUTPUT"
