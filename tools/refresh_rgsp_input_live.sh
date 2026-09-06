#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin

sh /vendor/bin/rgsp-input-prepare.sh
STAGE=/dev/rgsp-input-refresh
mkdir -p "$STAGE"
chmod 0700 "$STAGE"

# EventHub watches CREATE/DELETE, not attribute changes. Preserve each inode
# with a hard link, then recreate its original name to trigger rediscovery.
# The stage is on the same devtmpfs and is retained if restoration fails.
for node in /dev/input/event*; do
    [ -c "$node" ] || continue
    name=${node##*/}
    saved="$STAGE/$name"
    [ ! -e "$saved" ] || { echo "unresolved staged node: $saved" >&2; exit 1; }
    ln "$node" "$saved"
    rm "$node"
    ln "$saved" "$node" || { echo "restore $saved to $node manually" >&2; exit 1; }
    rm "$saved"
done
rmdir "$STAGE"
echo INPUT_REFRESH_COMPLETE
