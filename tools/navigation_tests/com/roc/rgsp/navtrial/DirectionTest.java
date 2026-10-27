package com.roc.rgsp.navtrial;

public final class DirectionTest {
    public static void main(String[] args) {
        int[][] boxes = {{0, 0, 100, 50}, {0, 60, 100, 110},
                {110, 60, 210, 110}, {0, 120, 100, 170}};
        check(Direction.next(boxes, 0, Direction.DOWN), 1);
        check(Direction.next(boxes, 1, Direction.DOWN), 3);
        check(Direction.next(boxes, 1, Direction.RIGHT), 2);
        check(Direction.next(boxes, 2, Direction.LEFT), 1);
        check(Direction.next(boxes, 1, Direction.UP), 0);
        check(Direction.next(boxes, 0, Direction.UP), -1);
        check(Direction.next(boxes, -1, Direction.DOWN), 0);
        check(Direction.next(new int[0][], -1, Direction.DOWN), -1);
        int[][] toolbar = {{10, 40, 80, 100}, {580, 40, 640, 100},
                {20, 115, 125, 180}};
        check(Direction.next(toolbar, 0, Direction.RIGHT), 1);
        check(Direction.next(toolbar, 0, Direction.DOWN), 2);
        int[][] bottomSlider = {{96, 430, 620, 458}, {656, 32, 720, 96}};
        check(Direction.next(bottomSlider, 0, Direction.RIGHT), 1);
        check(Direction.nextAligned(bottomSlider, 0, Direction.RIGHT), -1);
        int[][] sliderPeer = {{96, 430, 620, 458}, {656, 416, 720, 480}};
        check(Direction.nextAligned(sliderPeer, 0, Direction.RIGHT), 1);
        check(Direction.nextAligned(sliderPeer, 1, Direction.LEFT), 0);
        System.out.println("PASS: 14 directional navigation cases");
    }

    private static void check(int actual, int expected) {
        if (actual != expected) throw new AssertionError(actual + " != " + expected);
    }
}
