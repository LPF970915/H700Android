#!/usr/bin/env bash
set -euo pipefail

root=${1:?Android source root is required}
out="$root/out/soong"
removed=0

while IFS= read -r -d '' file; do
    magic=$(dd if="$file" bs=1 count=4 status=none 2>/dev/null | od -An -tx1 | tr -d ' \n')
    case "$magic" in
        7f454c46|213c6172) ;;
        *)
            printf 'remove corrupt output: %s (magic=%s)\n' "$file" "$magic"
            rm -f -- "$file"
            removed=$((removed + 1))
            ;;
    esac
done < <(find "$out" -type f \( -name '*.so' -o -name '*.o' -o -name '*.a' \) -print0)

printf 'removed=%s\n' "$removed"
