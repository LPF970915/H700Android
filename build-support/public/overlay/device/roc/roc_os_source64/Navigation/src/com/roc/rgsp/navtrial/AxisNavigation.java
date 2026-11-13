package com.roc.rgsp.navtrial;

import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/** Direction-axis ownership and a bounded continuous-navigation session. */
final class AxisNavigation {
    static final int UP = 19, DOWN = 20, LEFT = 21, RIGHT = 22;
    static final long FIRST_REPEAT_MS = 400;
    static final long REPEAT_MS = 160;
    static final long MAX_CONTINUOUS_MS = 10000;
    private static final int MAX_INPUTS = 16;
    private static final int HAT = 1, STICK = 2;

    private static final class Input {
        final int device, source;
        int hat, stick;
        boolean hatReady, stickReady;

        Input(int device, int source, boolean ready) {
            this.device = device;
            this.source = source;
            hatReady = stickReady = ready;
        }

        boolean neutral() { return hat == 0 && stick == 0; }
    }

    private final LinkedHashMap<Long, Input> inputs = new LinkedHashMap<>();
    private final Set<Integer> neutralForNewSourceDevices = new LinkedHashSet<>();
    private boolean newInputsNeedNeutral;
    private Input owner;
    private int ownerKind, direction;
    private long generation, startedAt, deadline;
    private long lastNow = Long.MIN_VALUE;
    private long immediateCount, repeatCount, capacityDrops;
    private String lastStop = "initial";

    /** Returns a direction only when this sample requires an immediate step. */
    int update(long now, int device, int source, int hatKey, int stickKey) {
        if (!time(now)) return 0;
        expire(now);
        Input input = input(device, source);
        if (input == null) return 0;
        input.hat = valid(hatKey);
        input.stick = valid(stickKey);
        if (input.hat == 0) input.hatReady = true;
        if (input.stick == 0) input.stickReady = true;

        if (owner != null && owner != input) {
            // An ignored held direction must not take over after the owner stops.
            blockNonNeutral(input);
            return 0;
        }

        if (owner != null) {
            if (ownerKind == HAT) {
                if (input.stick != 0) input.stickReady = false;
                if (input.hat == 0) {
                    stop("hat-neutral", false);
                    return 0;
                }
                return change(input.hat);
            }
            // A newly pressed digital HAT has priority over an analog stick.
            // This takeover retains the original continuous-session deadline.
            if (input.hat != 0 && input.hatReady) {
                if (input.stick != 0) input.stickReady = false;
                ownerKind = HAT;
                generation++;
                direction = input.hat;
                immediateCount++;
                return direction;
            }
            if (input.hat != 0) input.hatReady = false;
            if (input.stick == 0) {
                stop("stick-neutral", false);
                return 0;
            }
            return change(input.stick);
        }

        if (input.hat != 0 && input.hatReady) {
            if (input.stick != 0) input.stickReady = false;
            return start(now, input, HAT, input.hat);
        }
        if (input.stick != 0 && input.stickReady) {
            if (input.hat != 0) input.hatReady = false;
            return start(now, input, STICK, input.stick);
        }
        return 0;
    }

    /** The Android wrapper schedules the first call at 400ms, then every 160ms. */
    int repeat(long now) {
        if (!time(now)) return 0;
        expire(now);
        if (owner == null) return 0;
        repeatCount++;
        return direction;
    }

    void stop(String reason, boolean requireNeutral) {
        if (owner != null && requireNeutral) {
            if (ownerKind == HAT) owner.hatReady = false;
            else owner.stickReady = false;
            requireNewSourceNeutral(owner.device);
        }
        if (requireNeutral) {
            for (Input input : inputs.values()) {
                if (!input.neutral()) {
                    blockNonNeutral(input);
                    requireNewSourceNeutral(input.device);
                }
            }
        }
        owner = null;
        ownerKind = direction = 0;
        startedAt = deadline = 0;
        lastStop = reason == null ? "unspecified" : reason;
        generation++;
    }

    void cancel(int device, int source) {
        Input input = inputs.get(key(device, source));
        if (input != null) input.hatReady = input.stickReady = false;
        if (owner == input && input != null) stop("cancel", true);
    }

    void deviceChanged(int device) {
        requireNewSourceNeutral(device);
        for (Input input : inputs.values()) {
            if (input.device == device) input.hatReady = input.stickReady = false;
        }
        if (owner != null && owner.device == device) stop("device-changed", true);
    }

    boolean active() { return owner != null; }
    int direction() { return direction; }
    int ownerDevice() { return owner == null ? Integer.MIN_VALUE : owner.device; }
    int ownerSource() { return owner == null ? 0 : owner.source; }
    long generation() { return generation; }
    long remaining(long now) { return owner == null ? 0 : Math.max(0, deadline - now); }

    String describe(long now) {
        StringBuilder text = new StringBuilder();
        text.append("axisActive=").append(active()).append(" axisDirection=").append(direction)
                .append(" axisGeneration=").append(generation)
                .append(" axisOwner=").append(owner == null ? "none" : owner.device + "/" + owner.source)
                .append(" axisKind=").append(ownerKind == HAT ? "hat" : ownerKind == STICK ? "stick" : "none")
                .append(" axisStartedAt=").append(startedAt).append(" axisRemainingMs=").append(remaining(now))
                .append(" axisImmediate=").append(immediateCount).append(" axisRepeats=").append(repeatCount)
                .append(" axisStop=").append(lastStop).append(" axisInputs=").append(inputs.size())
                .append(" axisCapacityDrops=").append(capacityDrops).append(" axisGates=");
        for (Input input : inputs.values()) {
            text.append('[').append(input.device).append('/').append(input.source)
                    .append(" hat=").append(input.hat).append(':').append(input.hatReady ? "ready" : "neutral-required")
                    .append(" stick=").append(input.stick).append(':').append(input.stickReady ? "ready" : "neutral-required")
                    .append(']');
        }
        return text.toString();
    }

    private int start(long now, Input input, int kind, int key) {
        owner = input;
        ownerKind = kind;
        direction = key;
        startedAt = now;
        deadline = now > Long.MAX_VALUE - MAX_CONTINUOUS_MS ? Long.MAX_VALUE : now + MAX_CONTINUOUS_MS;
        generation++;
        immediateCount++;
        return key;
    }

    private int change(int key) {
        if (key == direction) return 0;
        direction = key;
        generation++;
        immediateCount++;
        return key;
    }

    private void expire(long now) {
        if (owner != null && now >= deadline) stop("continuous-limit", true);
    }

    private boolean time(long now) {
        if (now < lastNow) {
            stop("clock-backwards", true);
            return false;
        }
        lastNow = now;
        return true;
    }

    private static void blockNonNeutral(Input input) {
        if (input.hat != 0) input.hatReady = false;
        if (input.stick != 0) input.stickReady = false;
    }

    private void requireNewSourceNeutral(int device) {
        if (!neutralForNewSourceDevices.contains(device)) {
            if (neutralForNewSourceDevices.size() < MAX_INPUTS) neutralForNewSourceDevices.add(device);
            else newInputsNeedNeutral = true;
        }
    }

    private Input input(int device, int source) {
        long key = key(device, source);
        Input result = inputs.get(key);
        if (result != null) return result;
        if (inputs.size() >= MAX_INPUTS) {
            // Never evict a held or blocked input: doing so would forget its
            // neutral requirement and let a later sample reopen that stream.
            Iterator<Map.Entry<Long, Input>> iterator = inputs.entrySet().iterator();
            while (iterator.hasNext()) {
                Input old = iterator.next().getValue();
                if (old != owner && old.neutral() && old.hatReady && old.stickReady) {
                    iterator.remove();
                    break;
                }
            }
            if (inputs.size() >= MAX_INPUTS) {
                capacityDrops++;
                return null;
            }
        }
        result = new Input(device, source, !newInputsNeedNeutral && !neutralForNewSourceDevices.contains(device));
        inputs.put(key, result);
        return result;
    }

    private static int valid(int key) { return key >= UP && key <= RIGHT ? key : 0; }
    private static long key(int device, int source) { return ((long) device << 32) | (source & 0xffffffffL); }
}
