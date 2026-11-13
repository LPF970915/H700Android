package com.roc.rgsp.navtrial;

/** Regression sequences against the production, Android-independent state machine. */
public final class AxisNavigationTest {
    private static int checks;
    private static final int A = 7, B = 9, JOYSTICK = 0x01000010, OTHER_SOURCE = 0x02000010;
    private static final int U = AxisNavigation.UP, D = AxisNavigation.DOWN;
    private static final int L = AxisNavigation.LEFT, R = AxisNavigation.RIGHT;

    private static void equal(long expected, long actual, String message) {
        checks++;
        if (expected != actual) throw new AssertionError(message + ": expected " + expected + ", got " + actual);
    }
    private static void yes(boolean actual, String message) {
        checks++;
        if (!actual) throw new AssertionError(message);
    }
    private static int sample(AxisNavigation nav, long now, int hat, int stick) {
        return nav.update(now, A, JOYSTICK, hat, stick);
    }

    private static void normalHoldAndRelease() {
        AxisNavigation nav = new AxisNavigation();
        equal(D, sample(nav, 0, D, 0), "first physical direction is retained");
        equal(0, sample(nav, 50, D, 0), "duplicate sample is not another immediate step");
        equal(D, nav.repeat(400), "absolute-axis hold works without new MOVE");
        equal(D, nav.repeat(560), "normal repeat continues");
        equal(0, sample(nav, 570, 0, 0), "release emits no step");
        yes(!nav.active(), "release clears ownership");
        equal(0, nav.repeat(1000), "no repeat after release");
        equal(U, sample(nav, 1001, U, 0), "new direction works after neutral");

        nav = new AxisNavigation();
        equal(D, sample(nav, 0, D, 0), "short press begins immediately");
        sample(nav, 150, 0, 0);
        equal(0, nav.repeat(400), "a 150ms short press never gets a delayed repeat");
    }

    private static void capAndNeutralLatch() {
        AxisNavigation nav = new AxisNavigation();
        sample(nav, 0, D, 0);
        int steps = 1;
        for (long now = 400; now <= 10000; now += 160) if (nav.repeat(now) != 0) steps++;
        equal(61, steps, "ten-second maximum includes 61 total steps at normal schedule");
        yes(!nav.active(), "maximum clears active state");
        equal(0, sample(nav, 10001, D, 0), "held axis cannot restart after limit");
        equal(0, sample(nav, 10002, U, 0), "reverse noise cannot bypass neutral latch");
        nav.update(10003, B, JOYSTICK, 0, 0);
        equal(0, sample(nav, 10004, D, 0), "foreign neutral cannot unlock an expired owner");
        equal(0, nav.update(10005, A, OTHER_SOURCE, D, 0), "new source cannot bypass the expired device's gate");
        equal(0, nav.repeat(20000), "no periodic automatic restart");
        sample(nav, 20001, 0, 0);
        equal(D, sample(nav, 20002, D, 0), "release and repress recover normally");
        yes(nav.describe(20003).contains("axisStop=continuous-limit"), "stop diagnostic retained after restart");
    }

    private static void deadlineCannotBeExtended() {
        AxisNavigation nav = new AxisNavigation();
        sample(nav, 10, U, 0);
        equal(0, sample(nav, 9000, U, 0), "same MOVE does not restart");
        equal(D, sample(nav, 9500, D, 0), "direction reversal is immediate");
        equal(510, nav.remaining(9500), "reversal keeps original deadline");
        equal(D, nav.repeat(10009), "last pre-deadline repeat is permitted");
        equal(0, nav.repeat(10010), "deadline boundary stops");
        equal(0, sample(nav, 10011, U, 0), "new direction remains blocked at boundary");

        nav = new AxisNavigation();
        sample(nav, 0, 0, U);
        equal(D, sample(nav, 9900, D, U), "digital HAT can preempt analog owner");
        equal(100, nav.remaining(9900), "HAT takeover retains original deadline");
        equal(0, nav.repeat(10000), "kind takeover cannot renew the session");
    }

    private static void ownerIsolation() {
        AxisNavigation nav = new AxisNavigation();
        sample(nav, 0, D, 0);
        equal(A, nav.ownerDevice(), "active device accessor");
        equal(JOYSTICK, nav.ownerSource(), "active source accessor");
        equal(0, nav.update(10, B, JOYSTICK, 0, 0), "foreign neutral emits nothing");
        equal(D, nav.direction(), "foreign neutral cannot clear owner");
        nav.cancel(B, JOYSTICK);
        equal(D, nav.direction(), "foreign cancel cannot clear owner");
        equal(0, nav.update(20, A, OTHER_SOURCE, U, 0), "different source cannot take over");
        equal(D, nav.repeat(400), "owner repeat survives foreign samples");
        sample(nav, 410, 0, 0);
        equal(Integer.MIN_VALUE, nav.ownerDevice(), "inactive device sentinel");
        equal(0, nav.ownerSource(), "inactive source sentinel");
        equal(0, nav.update(420, A, OTHER_SOURCE, U, 0), "foreign direction observed while held requires neutral");
        nav.update(430, A, OTHER_SOURCE, 0, 0);
        equal(U, nav.update(440, A, OTHER_SOURCE, U, 0), "that source can start after its own neutral");
    }

    private static void independentKindsAndHandoff() {
        AxisNavigation nav = new AxisNavigation();
        equal(D, sample(nav, 0, D, U), "HAT has priority when both first appear");
        sample(nav, 10, 0, U);
        yes(!nav.active(), "HAT release does not fall through to held stick");
        equal(0, sample(nav, 20, 0, U), "already-held stick cannot take over on later MOVE");
        equal(D, sample(nav, 30, D, U), "bad stick cannot block a new HAT press");
        sample(nav, 40, 0, U);
        sample(nav, 50, 0, 0);
        equal(U, sample(nav, 60, 0, U), "stick is available after its own neutral");
        nav.stop("focus-lost", true);
        equal(0, sample(nav, 70, 0, U), "stopped analog owner must neutralize");
        equal(R, sample(nav, 80, R, U), "stopped analog owner does not block independent HAT");
    }

    private static void lifecycleAndGeneration() {
        AxisNavigation nav = new AxisNavigation();
        long initial = nav.generation();
        sample(nav, 0, D, 0);
        long started = nav.generation();
        yes(started > initial, "start invalidates old scheduled generations");
        sample(nav, 10, U, 0);
        yes(nav.generation() > started, "direction change invalidates stale callback");
        long changed = nav.generation();
        nav.stop("screen-off", true);
        yes(nav.generation() > changed, "stop invalidates the active callback");
        equal(0, nav.repeat(400), "screen-off callback cannot continue");
        equal(0, sample(nav, 500, U, 0), "wake with held axis remains disarmed");
        sample(nav, 510, 0, 0);
        equal(U, sample(nav, 520, U, 0), "wake recovers after actual neutral");
        nav.cancel(A, JOYSTICK);
        equal(0, sample(nav, 530, D, 0), "cancel locks a direction reversal too");
        sample(nav, 540, 0, 0);
        sample(nav, 550, D, 0);
        nav.deviceChanged(A);
        equal(0, sample(nav, 560, D, 0), "same-ID device change cannot inherit old state");
        equal(0, nav.update(570, A, OTHER_SOURCE, D, 0), "changed device also gates newly observed source");
        nav.update(580, A, OTHER_SOURCE, 0, 0);
        equal(D, nav.update(590, A, OTHER_SOURCE, D, 0), "changed source recovers after neutral");
        nav.deviceChanged(B);
        equal(D, nav.direction(), "unrelated device change does not clear active owner");
    }

    private static void gatesSurviveStopAndClockChecks() {
        AxisNavigation nav = new AxisNavigation();
        sample(nav, 10, D, 0);
        nav.stop("focus-lost", true);
        nav.stop("refresh-unmanaged", false);
        equal(0, sample(nav, 20, D, 0), "ordinary stop cannot erase a prior gate");
        sample(nav, 30, 0, 0);
        sample(nav, 40, U, 0);
        equal(0, nav.repeat(39), "backwards clock stops rather than extending state");
        equal(0, sample(nav, 41, U, 0), "clock error requires neutral");
        sample(nav, 42, 0, 0);
        equal(L, sample(nav, 43, L, 0), "clock error is recoverable");
        equal(0, sample(nav, 44, 123456, 0), "wrapper-invalid direction is neutral");
    }

    private static void lifecycleBlocksNonNeutralButPreservesKnownNeutralFirstPress() {
        AxisNavigation nav = new AxisNavigation();
        nav.update(0, A, JOYSTICK, 0, 0);
        nav.update(1, B, JOYSTICK, 0, 0);
        nav.stop("focus-lost-with-no-owner", true);
        equal(D, nav.update(2, A, JOYSTICK, D, 0), "known neutral channel keeps its first fresh press after focus loss");
        nav.update(3, B, JOYSTICK, U, 0);
        nav.stop("screen-off", true);
        equal(0, nav.update(4, B, JOYSTICK, U, 0), "non-owner residual direction stays gated after lifecycle stop");
        equal(0, nav.update(5, B, OTHER_SOURCE, U, 0), "residual device cannot reopen through a new source");
        nav.update(6, B, JOYSTICK, 0, 0);
        equal(U, nav.update(7, B, JOYSTICK, U, 0), "residual owner recovers after its own neutral");
        nav.stop("focus-lost", true);
        nav.stop("focus-lost-again-with-no-owner", true);
        equal(0, nav.update(8, B, JOYSTICK, U, 0), "repeated lifecycle stop does not erase residual gating");
        equal(R, nav.update(9, 99, JOYSTICK, R, 0), "completely unknown device intentionally retains its first direction");
    }

    private static void boundedMemoryDoesNotForgetBlockedInputs() {
        AxisNavigation nav = new AxisNavigation();
        for (int i = 0; i < 16; i++) {
            nav.update(i, i, JOYSTICK, D, 0);
            nav.cancel(i, JOYSTICK);
        }
        equal(0, nav.update(20, 100, JOYSTICK, U, 0), "full blocked table rejects an unknown input");
        yes(nav.describe(20).contains("axisInputs=16"), "input state is bounded at sixteen");
        yes(nav.describe(20).contains("axisCapacityDrops=1"), "capacity rejection is diagnosed");
        equal(0, nav.update(21, 0, JOYSTICK, D, 0), "blocked state was not evicted and reopened");
        nav.update(22, 0, JOYSTICK, 0, 0);
        equal(U, nav.update(23, 100, JOYSTICK, U, 0), "safe neutral entry can be evicted for a new input");
        yes(nav.describe(23).contains("axisInputs=16"), "replacement remains bounded");

        nav = new AxisNavigation();
        for (int i = 0; i < 17; i++) nav.deviceChanged(i);
        equal(0, nav.update(0, 999, JOYSTICK, D, 0), "bounded device-reset overflow fails closed for new streams");
        nav.update(1, 999, JOYSTICK, 0, 0);
        equal(D, nav.update(2, 999, JOYSTICK, D, 0), "overflow still allows real neutral recovery");
    }

    public static void main(String[] args) {
        equal(400, AxisNavigation.FIRST_REPEAT_MS, "first repeat constant");
        equal(160, AxisNavigation.REPEAT_MS, "repeat interval constant");
        equal(10000, AxisNavigation.MAX_CONTINUOUS_MS, "continuous limit constant");
        normalHoldAndRelease();
        capAndNeutralLatch();
        deadlineCannotBeExtended();
        ownerIsolation();
        independentKindsAndHandoff();
        lifecycleAndGeneration();
        gatesSurviveStopAndClockChecks();
        lifecycleBlocksNonNeutralButPreservesKnownNeutralFirstPress();
        boundedMemoryDoesNotForgetBlockedInputs();
        System.out.println("PASS: " + checks + " production AxisNavigation state-machine checks");
    }
}
