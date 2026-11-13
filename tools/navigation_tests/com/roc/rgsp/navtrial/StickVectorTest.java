package com.roc.rgsp.navtrial;

public final class StickVectorTest {
    private static void close(float got, float expected) {
        if (Math.abs(got - expected) > 0.0001f) throw new AssertionError(got + " != " + expected);
    }
    public static void main(String[] args) {
        close(StickVector.centered(0.10f, 0), 0);
        close(StickVector.centered(-0.15f, 0), 0);
        close(StickVector.centered(0.4f, 0.45f), 0);
        close(StickVector.centered(Float.NaN, 0), 0);
        close(StickVector.centered(Float.POSITIVE_INFINITY, 0), 0);
        close(StickVector.centered(1, 0), 1);
        close(StickVector.centered(-1, 0), -1);
        close(StickVector.centered(3, 0), 1);
        close(StickVector.centered(0.575f, 0), 0.5f);
        close(StickVector.bounded(0.2f, 0.2f, 0), 0.2f);
        close(StickVector.bounded(1, 1, 1), (float) Math.sqrt(0.5));
        System.out.println("PASS: 11 analog dead-zone, speed and diagonal checks");
    }
}
