package com.roc.rgsp.lid;

public final class LidStateTest {
    private static int assertions;
    private static void expect(LidState.Action expected, LidState.Action actual) {
        assertions++;
        if (expected != actual) throw new AssertionError("expected " + expected + ", got " + actual);
    }
    public static void main(String[] args) {
        LidState s = new LidState(250);
        expect(LidState.Action.NONE, s.observe(1, 0, false));
        expect(LidState.Action.NONE, s.observe(1, 250, false)); // startup cannot undo manual sleep
        expect(LidState.Action.NONE, s.observe(0, 300, true));
        expect(LidState.Action.NONE, s.observe(0, 549, true));
        expect(LidState.Action.SLEEP, s.observe(0, 550, true));
        expect(LidState.Action.NONE, s.observe(0, 900, true)); // no repeated/toggle sleep
        expect(LidState.Action.NONE, s.observe(1, 950, false));
        expect(LidState.Action.WAKE, s.observe(1, 1200, false));
        expect(LidState.Action.NONE, s.observe(1, 1450, false)); // no repeated wake

        s = new LidState(250);
        expect(LidState.Action.NONE, s.observe(0, 0, false));
        expect(LidState.Action.NONE, s.observe(0, 250, false)); // closed while already asleep
        expect(LidState.Action.NONE, s.observe(1, 300, true));
        expect(LidState.Action.NONE, s.observe(1, 550, true)); // open while already awake

        s = new LidState(250);
        expect(LidState.Action.NONE, s.observe(0, 0, true));
        expect(LidState.Action.NONE, s.observe(1, 100, true)); // bounce
        expect(LidState.Action.NONE, s.observe(0, 150, true));
        expect(LidState.Action.NONE, s.observe(-1, 390, true)); // read error resets debounce
        expect(LidState.Action.NONE, s.observe(0, 400, true));
        expect(LidState.Action.NONE, s.observe(2, 640, true)); // invalid value
        expect(LidState.Action.NONE, s.observe(0, 650, true));
        expect(LidState.Action.SLEEP, s.observe(0, 900, true));
        expect(LidState.Action.NONE, s.observe(0, 1000, true));
        expect(LidState.Action.NONE, s.observe(1, 1100, false));
        expect(LidState.Action.NONE, s.observe(1, 100, false)); // clock rollback restarts debounce
        expect(LidState.Action.NONE, s.observe(1, 349, false));
        expect(LidState.Action.WAKE, s.observe(1, 350, false));
        System.out.println("H700_LID_STATE_PASS assertions=" + assertions);
    }
}
