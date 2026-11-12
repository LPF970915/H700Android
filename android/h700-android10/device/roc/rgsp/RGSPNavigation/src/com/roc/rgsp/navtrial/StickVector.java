package com.roc.rgsp.navtrial;

/** Analog dead zone and bounded movement, independent of Android for host tests. */
final class StickVector {
    static float centered(float value, float flat) {
        if (Float.isNaN(value) || Float.isInfinite(value)) return 0;
        float dead = Math.max(0.15f, Math.min(0.5f, flat));
        float magnitude = Math.min(1, Math.abs(value));
        return magnitude <= dead ? 0 : Math.copySign((magnitude - dead) / (1 - dead), value);
    }

    static float bounded(float component, float x, float y) {
        return (float) (component / Math.max(1, Math.hypot(x, y)));
    }
}
