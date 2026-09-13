package com.roc.rgsp.navtrial;

final class Direction {
    static final int UP = 19, DOWN = 20, LEFT = 21, RIGHT = 22;

    static int next(int[][] boxes, int current, int direction) {
        if (boxes.length == 0) return -1;
        if (current < 0 || current >= boxes.length) return 0;
        int[] from = boxes[current];
        double x = (from[0] + from[2]) / 2.0;
        double y = (from[1] + from[3]) / 2.0;
        int best = -1;
        boolean bestAligned = false;
        double bestScore = Double.MAX_VALUE;
        for (int i = 0; i < boxes.length; i++) {
            if (i == current) continue;
            int[] to = boxes[i];
            double dx = (to[0] + to[2]) / 2.0 - x;
            double dy = (to[1] + to[3]) / 2.0 - y;
            double major = direction == UP ? -dy : direction == DOWN ? dy
                    : direction == LEFT ? -dx : dx;
            double minor = direction == UP || direction == DOWN ? dx : dy;
            if (major < 2) continue;
            boolean aligned = direction == UP || direction == DOWN
                    ? from[0] < to[2] && to[0] < from[2]
                    : from[1] < to[3] && to[1] < from[3];
            double score = major * major + 4 * minor * minor;
            if ((aligned && !bestAligned) || (aligned == bestAligned && score < bestScore)) {
                bestScore = score;
                bestAligned = aligned;
                best = i;
            }
        }
        return best;
    }
}
