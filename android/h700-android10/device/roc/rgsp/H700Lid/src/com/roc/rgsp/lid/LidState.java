package com.roc.rgsp.lid;

/** A debounced edge detector. Invalid samples never create a power action. */
public final class LidState {
    public static final int UNKNOWN = -1, CLOSED = 0, OPEN = 1;
    public enum Action { NONE, SLEEP, WAKE }
    private final long debounceMs;
    private int candidate = UNKNOWN, stable = UNKNOWN;
    private long candidateSince;

    public LidState(long debounceMs) {
        if (debounceMs < 0) throw new IllegalArgumentException("negative debounce");
        this.debounceMs = debounceMs;
    }

    public Action observe(int value, long now, boolean interactive) {
        if (value != CLOSED && value != OPEN) {
            candidate = UNKNOWN;
            return Action.NONE;
        }
        if (candidate != value || now < candidateSince) {
            candidate = value;
            candidateSince = now;
            return Action.NONE;
        }
        if (now - candidateSince < debounceMs || stable == value) return Action.NONE;
        int previous = stable;
        stable = value;
        if (value == CLOSED) return interactive ? Action.SLEEP : Action.NONE;
        // Service startup/restart with an open lid must not undo manual sleep.
        return previous == CLOSED && !interactive ? Action.WAKE : Action.NONE;
    }

    public int stable() { return stable; }
}
