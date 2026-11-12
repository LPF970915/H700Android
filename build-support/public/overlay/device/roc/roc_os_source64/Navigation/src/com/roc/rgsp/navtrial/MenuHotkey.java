package com.roc.rgsp.navtrial;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** Physical Menu: short release goes Home, a hold opens Quick Settings once. */
final class MenuHotkey {
    static final int PASS = 0, CONSUME = 1, HOME = 2, QUICK_SETTINGS = 3;
    static final long HOLD_MS = 700;
    private static final class Press {
        final long started;
        boolean cancelled, fired;
        Press(long started, boolean cancelled) { this.started = started; this.cancelled = cancelled; }
    }
    private final Map<Integer, Press> presses = new HashMap<>();
    private final Map<Integer, Set<Integer>> held = new HashMap<>();

    static boolean isMenu(int key, int scan, boolean fallback) {
        // Android MENU (82) is also Select's fallback. Never bind it here.
        return key == 110 || (fallback && key == 3 && scan == 312);
    }

    int update(int device, int key, int scan, boolean fallback,
            boolean down, boolean cancelled, long when) {
        if (!isMenu(key, scan, fallback)) {
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
            return PASS;
        }
        if (down) {
            Press press = presses.get(device);
            if (press == null) presses.put(device, new Press(when, cancelled || held.containsKey(device)));
            else if (cancelled) press.cancelled = true;
            return CONSUME;
        }
        Press press = presses.remove(device);
        if (press == null || press.cancelled || press.fired || cancelled) return CONSUME;
        return when - press.started >= HOLD_MS ? QUICK_SETTINGS : HOME;
    }

    long nextDelay(long now) {
        long delay = Long.MAX_VALUE;
        for (Press press : presses.values()) if (!press.cancelled && !press.fired)
            delay = Math.min(delay, Math.max(0, HOLD_MS - Math.max(0, now - press.started)));
        return delay == Long.MAX_VALUE ? -1 : delay;
    }

    boolean fireLong(long now) {
        boolean fire = false;
        for (Press press : presses.values()) if (!press.cancelled && !press.fired
                && now - press.started >= HOLD_MS) { press.fired = true; fire = true; }
        return fire;
    }

    void clear() { presses.clear(); held.clear(); }
}
