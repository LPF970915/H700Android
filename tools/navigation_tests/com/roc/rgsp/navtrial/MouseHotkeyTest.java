package com.roc.rgsp.navtrial;

public final class MouseHotkeyTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) {
        MouseHotkey h = new MouseHotkey();
        check(MouseHotkey.canonicalKey(82, 310, true) == 109);
        check(MouseHotkey.canonicalKey(82, 310, false) == 82);
        check(MouseHotkey.canonicalKey(23, 311, true) == 23);
        check(!h.update(1, 109, true, false, 0));
        check(!h.update(1, 109, false, false, 1999));
        check("short".equals(h.lastResult));
        check(!h.update(1, 109, true, false, 3000));
        check(!h.update(1, 109, true, false, 4500)); // repeat keeps the initial timestamp
        check(h.update(1, 109, false, false, 5000)); // exact threshold, only on release
        check(!h.update(1, 109, false, false, 5001)); // duplicate UP cannot toggle twice

        h.update(1, 109, true, false, 6000);
        h.update(1, 108, true, false, 6100); // Select+Start must remain an app chord
        h.update(1, 108, false, false, 6200);
        check(!h.update(1, 109, false, false, 9000)); // releasing Start does not re-arm
        check("cancelled".equals(h.lastResult));
        h.update(1, 108, true, false, 10000);
        h.update(1, 109, true, false, 10100); // Start held before Select also blocks it
        h.update(1, 108, false, false, 10200);
        check(!h.update(1, 109, false, false, 13000));

        h.update(1, 109, true, false, 14000);
        h.update(2, 108, true, false, 14100); // another controller cannot cancel this hold
        check(h.update(1, 109, false, false, 16000));
        h.clear();
        h.update(1, 109, true, false, 17000);
        check(!h.update(1, 109, false, true, 20000));
        h.update(1, 109, true, true, 21000);
        check(!h.update(1, 109, false, false, 24000));
        h.update(1, 109, true, false, 25000); h.cancel();
        check(!h.update(1, 109, false, false, 28000));
        h.update(1, 109, true, false, 29000); h.clear();
        check(!h.update(1, 109, false, false, 32000));

        // The previous shoulder chord is no longer recognized.
        h.update(1, 102, true, false, 33000); h.update(1, 103, true, false, 33001);
        check(!h.update(1, 108, true, false, 33002));
        h.clear();
        h.update(1, 109, true, false, 40000);
        check(!h.update(1, 109, false, false, 39000)); // reversed clock is never long
        System.out.println("PASS: Select 2s threshold, repeat/duplicate, both chord orders, per-device, cancel/reset cases");
    }
}
