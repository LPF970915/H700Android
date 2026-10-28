package com.roc.rgsp.navtrial;

public final class MouseHotkeyTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) {
        MouseHotkey h = new MouseHotkey();
        check(!h.update(1, 109, true, false)); // Select remains entirely unclaimed
        check(!h.update(1, 109, false, false));
        check(!h.update(1, 102, true, false));
        check(!h.update(2, 103, true, false));
        check(!h.update(1, 108, true, false)); // never combine two controllers
        h.update(1, 108, false, false);
        h.update(1, 103, true, false);
        check(h.update(1, 108, true, false));
        check(!h.update(1, 108, true, false)); // repeat must not toggle again
        h.update(1, 108, false, false);
        check(h.update(1, 108, true, false)); // next tap can close the mode
        h.update(1, 108, false, false);
        h.update(1, 103, false, false);
        check(!h.update(1, 108, true, false));
        h.clear();
        h.update(1, 108, true, false);
        h.update(1, 102, true, false); h.update(1, 103, true, false);
        check(!h.update(1, 108, true, false)); // Start must be pressed last
        h.clear();
        h.update(1, 102, true, false); h.update(1, 103, true, false);
        check(!h.update(1, 108, true, true)); // cancelled event cannot arm
        h.clear(); check(!h.update(1, 108, true, false));
        System.out.println("PASS: Select passthrough, same-device chord, repeat/release/order/cancel/reset cases");
    }
}
