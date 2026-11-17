package com.roc.rgsp.navtrial;

import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

/** Physical DPAD ownership; external repeat/downTime values cannot renew a hold. */
final class KeyNavigation {
    static final int CONSUME = 0, STEP = 1;
    static final long FIRST_REPEAT_MS = 400, REPEAT_MS = 160, MAX_CONTINUOUS_MS = 10000;
    private static final int MAX_INPUTS = 32;

    private static final class Input {
        final int device, source, key, scan;
        boolean timeoutDebt;
        long lastEvent;
        Input(int device, int source, int key, int scan, long eventTime) {
            this.device = device; this.source = source; this.key = key; this.scan = scan;
            lastEvent = eventTime;
        }
    }

    private final LinkedHashMap<String, Input> inputs = new LinkedHashMap<>();
    private Input owner;
    private long startedAt, deadline, nextAt, generation, lastNow = Long.MIN_VALUE;
    private long boundaryAt, lastDownEvent = Long.MIN_VALUE;
    private long immediateCount, repeatCount, ignoredDowns, capacityDrops;
    private boolean limited, overflowDebt;
    private String lastStop = "initial";

    static boolean direction(int key) { return key >= 19 && key <= 22; }

    int down(long now, long eventTime, int device, int source, int key, int scan, int rawRepeatCount) {
        if (!direction(key) || !time(now)) return CONSUME;
        expire(now);
        if (!validDown(now, eventTime)) return CONSUME;
        String identity = identity(device, source, key, scan);
        Input input = inputs.get(identity);
        if (input != null) { input.lastEvent = eventTime; ignoredDowns++; return CONSUME; }
        input = add(device, source, key, scan, eventTime);
        if (input == null) return CONSUME;
        if (limited) { input.timeoutDebt = true; ignoredDowns++; return CONSUME; }
        // A repeat without its first DOWN cannot establish a new owner. A second
        // physical direction is also held until its own UP, never a takeover.
        if (owner != null || rawRepeatCount != 0) { ignoredDowns++; return CONSUME; }
        owner = input;
        startedAt = eventTime;
        deadline = addTime(eventTime, MAX_CONTINUOUS_MS);
        nextAt = addTime(eventTime, FIRST_REPEAT_MS);
        generation++;
        immediateCount++;
        return STEP;
    }

    /** Observe unusable/stale input without starting a navigation session. */
    void blockedDown(long now, long eventTime, int device, int source, int key, int scan) {
        if (!direction(key) || !time(now)) return;
        expire(now);
        if (!validDown(now, eventTime)) return;
        Input input = inputs.get(identity(device, source, key, scan));
        if (input == null) input = add(device, source, key, scan, eventTime);
        if (input != null) input.lastEvent = eventTime;
        if (input != null && limited) input.timeoutDebt = true;
    }

    /** A canceled UP is a focus cancellation, not proof of physical release. */
    boolean up(long now, long eventTime, int device, int source, int key, int scan, boolean canceled) {
        String identity = identity(device, source, key, scan);
        Input input = inputs.get(identity);
        if (input == null) return false;
        if (!time(now)) return true;
        expire(now);
        if (eventTime < input.lastEvent || eventTime < 0 || eventTime > now) return true;
        if (canceled && input.timeoutDebt) return true;
        inputs.remove(identity);
        if (owner == input) finish(canceled ? "canceled-up" : "physical-up");
        updateLimited();
        return true;
    }

    /** Called only by the local 400/160ms scheduler, never by raw DOWN events. */
    int repeat(long now) {
        if (!time(now)) return 0;
        expire(now);
        if (owner == null || now < nextAt) return 0;
        nextAt = addTime(now, REPEAT_MS);
        repeatCount++;
        return owner.key;
    }

    /** Context changes retire ordinary holds without inventing a release debt. */
    void stop(long now, String reason) {
        expire(now);
        boundaryAt = Math.max(boundaryAt, now);
        finish(reason);
        Iterator<Map.Entry<String, Input>> iterator = inputs.entrySet().iterator();
        while (iterator.hasNext()) if (!iterator.next().getValue().timeoutDebt) iterator.remove();
        updateLimited();
    }

    void deviceChanged(int device) {
        if (owner != null && owner.device == device) finish("device-changed");
        Iterator<Map.Entry<String, Input>> iterator = inputs.entrySet().iterator();
        while (iterator.hasNext()) {
            Input input = iterator.next().getValue();
            if (input.device == device && !input.timeoutDebt) iterator.remove();
        }
        updateLimited();
    }

    boolean active() { return owner != null; }
    int ownerDevice() { return owner == null ? Integer.MIN_VALUE : owner.device; }
    long generation() { return generation; }
    long nextDelay(long now) { return owner == null ? -1 : Math.max(0, Math.min(nextAt, deadline) - now); }

    String describe(long now) {
        return "keyActive=" + active() + " keyGeneration=" + generation
                + " keyOwner=" + (owner == null ? "none" : identity(owner.device, owner.source, owner.key, owner.scan))
                + " keyStartedAt=" + startedAt + " keyRemainingMs=" + (owner == null ? 0 : Math.max(0, deadline - now))
                + " keyImmediate=" + immediateCount + " keyRepeats=" + repeatCount
                + " keyIgnoredDowns=" + ignoredDowns + " keyLimited=" + limited
                + " keyTracked=" + inputs.size() + " keyCapacityDrops=" + capacityDrops + " keyStop=" + lastStop;
    }

    private Input add(int device, int source, int key, int scan, long eventTime) {
        if (inputs.size() >= MAX_INPUTS) {
            capacityDrops++;
            // Never forget a timed-out identity to make room for another DOWN.
            if (limited) overflowDebt = true;
            return null;
        }
        Input input = new Input(device, source, key, scan, eventTime);
        inputs.put(identity(device, source, key, scan), input);
        return input;
    }

    private void expire(long now) {
        if (owner == null || now < deadline) return;
        for (Input input : inputs.values()) input.timeoutDebt = true;
        limited = true;
        finish("continuous-limit");
    }

    private void finish(String reason) {
        owner = null;
        startedAt = deadline = nextAt = 0;
        generation++;
        lastStop = reason == null ? "unspecified" : reason;
    }

    private boolean time(long now) {
        if (now < lastNow) { stop(lastNow, "clock-backwards"); return false; }
        lastNow = now;
        return true;
    }

    private boolean validDown(long now, long eventTime) {
        if (eventTime < 0 || eventTime > now || eventTime < boundaryAt || eventTime < lastDownEvent
                || now - eventTime >= MAX_CONTINUOUS_MS) return false;
        lastDownEvent = eventTime;
        return true;
    }

    private void updateLimited() {
        limited = overflowDebt;
        for (Input input : inputs.values()) limited |= input.timeoutDebt;
    }

    private static long addTime(long now, long delay) {
        return now > Long.MAX_VALUE - delay ? Long.MAX_VALUE : now + delay;
    }
    private static String identity(int device, int source, int key, int scan) {
        return device + "/" + source + "/" + key + "/" + scan;
    }
}
