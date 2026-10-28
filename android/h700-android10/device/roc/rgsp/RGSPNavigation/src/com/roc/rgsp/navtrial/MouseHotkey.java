package com.roc.rgsp.navtrial;

import java.util.HashMap;
import java.util.Map;

/** Same-controller L1 + R1, then a fresh Start down. No Select reservation. */
final class MouseHotkey {
    static final int L1 = 102, R1 = 103, START = 108;
    private final Map<Integer, Integer> held = new HashMap<>();

    boolean update(int device, int key, boolean down, boolean cancelled) {
        int bit = key == L1 ? 1 : key == R1 ? 2 : key == START ? 4 : 0;
        if (bit == 0) return false;
        int before = held.getOrDefault(device, 0);
        int after = down && !cancelled ? before | bit : before & ~bit;
        if (after == 0) held.remove(device); else held.put(device, after);
        return down && !cancelled && bit == 4 && (before & 3) == 3 && (before & 4) == 0;
    }

    void clear() { held.clear(); }
}
