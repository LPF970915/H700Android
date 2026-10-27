package com.roc.rgsp.navtrial;

/** Match recycled list controls without confusing identical captions. */
final class FocusIdentity {
    static int find(String[] keys, boolean[] sameNode, String selected) {
        if (selected == null) return -1;
        for (int i = 0; i < keys.length; i++) {
            if (sameNode[i] && selected.equals(keys[i])) return i;
        }
        for (int i = 0; i < keys.length; i++) {
            if (selected.equals(keys[i])) return i;
        }
        // A unique semantic item can move when new rows are inserted above it.
        // Ambiguous captions require their original collection position.
        int match = -1;
        String semantic = semantic(selected);
        for (int i = 0; i < keys.length; i++) {
            if (!semantic.equals(semantic(keys[i]))) continue;
            if (match >= 0) return -1;
            match = i;
        }
        return match;
    }

    private static String semantic(String key) {
        int position = key.lastIndexOf("|#collection=");
        return position < 0 ? key : key.substring(0, position);
    }
}
