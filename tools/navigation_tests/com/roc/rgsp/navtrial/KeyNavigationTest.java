package com.roc.rgsp.navtrial;

/** Host regression checks for the exact production physical-DPAD controller. */
public final class KeyNavigationTest {
    static int checks;
    static final int DEVICE = 7, SOURCE = 0x101, LEFT = 21, RIGHT = 22;
    static void check(boolean value, String reason) {
        checks++; if (!value) throw new AssertionError(reason);
    }
    static int down(KeyNavigation keys, long now, int key) {
        return keys.down(now, now, DEVICE, SOURCE, key, key + 100, 0);
    }
    static boolean up(KeyNavigation keys, long now, int key, boolean canceled) {
        return keys.up(now, now, DEVICE, SOURCE, key, key + 100, canceled);
    }

    static void localTiming() {
        KeyNavigation keys = new KeyNavigation();
        check(down(keys, 100, LEFT) == KeyNavigation.STEP, "short press acts immediately");
        check(keys.nextDelay(100) == 400, "first local repeat waits 400ms");
        check(keys.repeat(499) == 0, "no early repeat");
        check(keys.repeat(500) == LEFT, "repeat at 400ms");
        check(keys.nextDelay(500) == 160, "subsequent local repeat waits 160ms");
        check(down(keys, 501, LEFT) == KeyNavigation.CONSUME, "external zero-count DOWN is consumed");
        check(keys.nextDelay(501) == 159, "raw DOWN cannot postpone local repeat");
        check(keys.repeat(659) == 0 && keys.repeat(660) == LEFT, "repeat remains 160ms");
        check(up(keys, 661, LEFT, false) && !keys.active(), "real release stops immediately");
        check(keys.repeat(1000) == 0, "no navigation after release");
    }

    static void rawZeroCannotRenewDeadline() {
        KeyNavigation keys = new KeyNavigation();
        check(down(keys, 0, LEFT) == KeyNavigation.STEP, "initial raw DOWN");
        for (int time = 100; time < 10000; time += 100)
            check(down(keys, time, LEFT) == KeyNavigation.CONSUME, "InputReader-like zero count cannot renew");
        check(keys.repeat(9999) == LEFT, "owner is still valid just before absolute cap");
        check(keys.repeat(10000) == 0 && !keys.active(), "absolute 10s cap retires owner");
        check(down(keys, 10001, LEFT) == KeyNavigation.CONSUME, "held zero-count DOWN stays blocked");
        check(up(keys, 10002, LEFT, true), "fabricated canceled release is observed");
        check(down(keys, 10003, LEFT) == KeyNavigation.CONSUME, "canceled release cannot clear timeout debt");
        check(up(keys, 10004, LEFT, false), "real release clears debt");
        check(down(keys, 10005, LEFT) == KeyNavigation.STEP, "next physical press restarts");
    }

    static void blockedInputsRequireTheirOwnRelease() {
        KeyNavigation keys = new KeyNavigation();
        check(down(keys, 0, LEFT) == KeyNavigation.STEP, "first direction owns session");
        check(down(keys, 100, RIGHT) == KeyNavigation.CONSUME, "second direction cannot take over");
        check(keys.down(101, 101, 8, SOURCE, RIGHT, 122, 0) == KeyNavigation.CONSUME, "second device cannot take over");
        check(keys.repeat(10000) == 0, "all held identities reach same cap");
        check(keys.down(10001, 10001, DEVICE, SOURCE + 1, RIGHT, 122, 0) == KeyNavigation.CONSUME,
                "new source during timeout records release debt");
        check(keys.down(10002, 10002, DEVICE, SOURCE, LEFT, 999, 0) == KeyNavigation.CONSUME,
                "same key on another scan is independently held");
        check(up(keys, 10003, LEFT, false), "release original owner");
        check(down(keys, 10004, LEFT) == KeyNavigation.CONSUME, "other blocked identities still require release");
        check(up(keys, 10005, LEFT, false), "release newly blocked original key");
        check(up(keys, 10006, RIGHT, false), "release second direction");
        check(keys.up(10007, 10007, 8, SOURCE, RIGHT, 122, false), "release second device");
        check(keys.up(10008, 10008, DEVICE, SOURCE + 1, RIGHT, 122, false), "release second source");
        check(keys.up(10009, 10009, DEVICE, SOURCE, LEFT, 999, false), "release second scan");
        check(down(keys, 10010, RIGHT) == KeyNavigation.STEP, "all real releases recover normal input");
    }

    static void contextAndCancel() {
        KeyNavigation keys = new KeyNavigation();
        check(down(keys, 10, LEFT) == KeyNavigation.STEP, "start ordinary context session");
        long generation = keys.generation();
        keys.stop(20, "window-change");
        check(!keys.active() && keys.generation() != generation, "context stop retires generation");
        check(keys.down(21, 19, DEVICE, SOURCE, LEFT, 121, 0) == KeyNavigation.CONSUME, "old context event is rejected");
        check(keys.down(22, 22, DEVICE, SOURCE, LEFT, 121, 1) == KeyNavigation.CONSUME,
                "native repeat cannot establish a replacement session");
        check(up(keys, 23, LEFT, true), "ordinary canceled UP clears soft repeat observation");
        check(down(keys, 24, LEFT) == KeyNavigation.STEP, "ordinary focus cancellation invents no timeout debt");
        check(up(keys, 25, LEFT, true) && !keys.active(), "ordinary cancellation stops existing hold");
        check(down(keys, 26, LEFT) == KeyNavigation.STEP, "fresh ordinary key recovers");
        keys.stop(10026, "screen-off-at-cap");
        check(down(keys, 10027, LEFT) == KeyNavigation.CONSUME, "context stop cannot erase an elapsed cap");
        keys.stop(10028, "screen-on");
        check(up(keys, 10029, LEFT, true), "canceled UP after wake stays owned");
        check(down(keys, 10030, LEFT) == KeyNavigation.CONSUME, "wake does not clear timeout debt");
        check(up(keys, 10031, LEFT, false), "real release after wake");
        check(down(keys, 10032, LEFT) == KeyNavigation.STEP, "new press after real release works");
    }

    static void eventTimeAndReleaseIdentity() {
        KeyNavigation keys = new KeyNavigation();
        check(keys.down(1000, -1, DEVICE, SOURCE, LEFT, 121, 0) == KeyNavigation.CONSUME, "negative time rejected");
        check(keys.down(1000, 1001, DEVICE, SOURCE, LEFT, 121, 0) == KeyNavigation.CONSUME, "future time rejected");
        check(keys.down(11000, 1000, DEVICE, SOURCE, LEFT, 121, 0) == KeyNavigation.CONSUME, "already-expired queued first DOWN rejected");
        check(keys.down(11001, 10002, DEVICE, SOURCE, LEFT, 121, 0) == KeyNavigation.STEP, "valid queued press can act once");
        check(keys.nextDelay(11001) == 0, "queued event keeps its original first-repeat time");
        check(keys.repeat(20002) == 0, "queued first DOWN does not gain another 10s on delivery");
        check(!keys.up(20003, 20003, DEVICE, SOURCE, LEFT, 999, false), "wrong scan UP cannot clear owner debt");
        check(keys.up(20004, 10001, DEVICE, SOURCE, LEFT, 121, false), "stale matching UP is swallowed");
        check(down(keys, 20005, LEFT) == KeyNavigation.CONSUME, "stale UP did not rearm");
        check(keys.up(20006, 20006, DEVICE, SOURCE, LEFT, 121, false), "ordered physical UP clears debt");
        check(keys.down(20007, 20004, DEVICE, SOURCE, RIGHT, 122, 0) == KeyNavigation.CONSUME, "out-of-order DOWN rejected");
        check(down(keys, 20008, RIGHT) == KeyNavigation.STEP, "ordered new direction starts");
    }

    static void lifecycleAndBlockedObservation() {
        KeyNavigation keys = new KeyNavigation();
        keys.blockedDown(10, 10, DEVICE, SOURCE, LEFT, 121);
        check(!keys.active(), "blocked observation never starts a timer");
        check(down(keys, 11, LEFT) == KeyNavigation.CONSUME, "observed blocked direction waits for release");
        keys.stop(12, "unmanaged");
        check(down(keys, 13, LEFT) == KeyNavigation.STEP, "ordinary context transition has no permanent debt");
        keys.deviceChanged(99);
        check(keys.active(), "unrelated device notification does not stop owner");
        keys.deviceChanged(DEVICE);
        check(!keys.active(), "owner device notification stops owner");
        check(down(keys, 14, LEFT) == KeyNavigation.STEP, "new device generation can receive fresh input");
        check(keys.repeat(13) == 0 && !keys.active(), "backward clock cannot navigate or resurrect owner");
    }

    public static void main(String[] args) {
        localTiming(); rawZeroCannotRenewDeadline(); blockedInputsRequireTheirOwnRelease();
        contextAndCancel(); eventTimeAndReleaseIdentity(); lifecycleAndBlockedObservation();
        System.out.println("PASS: " + checks + " production KeyNavigation timing checks");
    }
}
