package com.roc.rgsp.navtrial;

public final class PointerPositionTest {
    public static void main(String[] args) {
        PointerPosition point = new PointerPosition();
        point.resize(720, 480);
        if (point.x != 359.5f || point.y != 239.5f) throw new AssertionError();
        point.move(1000, 1000);
        if (point.x != 719f || point.y != 479f) throw new AssertionError();
        point.resize(640, 480);
        if (point.x != 639f || point.y != 479f) throw new AssertionError();
        point.move(-639, -479);
        point.resize(720, 720);
        if (point.x != 0f || point.y != 0f) throw new AssertionError();
        System.out.println("PASS: dynamic pointer geometry 720x480 -> 640x480 -> 720x720");
    }
}
