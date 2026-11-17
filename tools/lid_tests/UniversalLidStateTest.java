package com.roc.rgsp.lid;

public final class UniversalLidStateTest {
    private static int checks;
    private static void expect(LidState.Action expected, LidState.Action actual) {
        checks++;
        if (expected != actual) throw new AssertionError(expected + " != " + actual);
    }
    public static void main(String[] args) {
        LidState state = new LidState(250);
        // A flat handheld's unused Hall pin may be low throughout a session.
        for (int i=0; i<3600; i++)
            expect(LidState.Action.NONE, state.observe(0, i*250L, true));
        expect(LidState.Action.NONE, state.observe(1, 1000000, true));
        expect(LidState.Action.NONE, state.observe(1, 1000250, true));
        expect(LidState.Action.NONE, state.observe(0, 1000500, true));
        expect(LidState.Action.NONE, state.observe(0, 1000749, true));
        expect(LidState.Action.SLEEP, state.observe(0, 1000750, true));
        expect(LidState.Action.NONE, state.observe(0, 1001000, false));
        expect(LidState.Action.NONE, state.observe(1, 1001250, false));
        expect(LidState.Action.WAKE, state.observe(1, 1001500, false));
        expect(LidState.Action.NONE, state.observe(-1, 1001750, true));
        expect(LidState.Action.NONE, state.observe(0, 1002000, true));
        expect(LidState.Action.NONE, state.observe(-1, 1002200, true));
        expect(LidState.Action.NONE, state.observe(0, 1002400, true));
        expect(LidState.Action.SLEEP, state.observe(0, 1002650, true));
        System.out.println("UNIVERSAL_HALL_EDGE_PASS checks="+checks);
    }
}
