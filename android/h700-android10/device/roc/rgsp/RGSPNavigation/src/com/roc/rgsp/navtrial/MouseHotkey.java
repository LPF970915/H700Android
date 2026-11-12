package com.roc.rgsp.navtrial;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** A standalone Select hold, accepted on release. Other buttons cancel it. */
final class MouseHotkey {
    static final int SELECT = 109;
    static final long HOLD_MS = 2000;
    private static final class Press {
        final long started;
        boolean cancelled;
        Press(long started, boolean cancelled) {
            this.started = started;
            this.cancelled = cancelled;
        }
    }
    private final Map<Integer, Press> presses = new HashMap<>();
    private final Map<Integer, Set<Integer>> held = new HashMap<>();
    long lastHoldMs;
    String lastResult = "none";

    static int canonicalKey(int key, int scan, boolean fallback) {
        // Generic.kcm turns an unhandled physical Select into MENU. It is
        // another delivery of the same button, not a second chord member.
        return fallback && scan == 310 && key == 82 ? SELECT : key;
    }

    boolean update(int device, int key, boolean down, boolean cancelled, long when) {
        if (key != SELECT) {
            if (down && !cancelled) {
                held.computeIfAbsent(device, ignored -> new HashSet<>()).add(key);
                Press press = presses.get(device);
                if (press != null) press.cancelled = true;
            } else {
                Set<Integer> keys = held.get(device);
                if (keys != null) {
                    keys.remove(key);
                    if (keys.isEmpty()) held.remove(device);
                }
            }
            return false;
        }
        if (down) {
            Press press = presses.get(device);
            if (press == null) {
                presses.put(device, new Press(when, cancelled || held.containsKey(device)));
            } else if (cancelled) {
                press.cancelled = true;
            }
            return false;
        }
        Press press = presses.remove(device);
        if (press == null) return false;
        lastHoldMs = Math.max(0, when - press.started);
        boolean accepted = !cancelled && !press.cancelled && lastHoldMs >= HOLD_MS;
        lastResult = accepted ? "accepted" : cancelled || press.cancelled ? "cancelled" : "short";
        return accepted;
    }

    void cancel() {
        for (Press press : presses.values()) press.cancelled = true;
    }

    void clear() { presses.clear(); held.clear(); }
}
