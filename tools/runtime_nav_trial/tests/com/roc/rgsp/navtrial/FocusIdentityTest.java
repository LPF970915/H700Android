package com.roc.rgsp.navtrial;

public final class FocusIdentityTest {
    private static int checks;
    private static void check(int expected, String selected, String[] keys, boolean... sameNode) {
        int actual = FocusIdentity.find(keys, sameNode, selected);
        if (actual != expected) throw new AssertionError("Expected " + expected + ", got " + actual);
        checks++;
    }
    private static String key(String caption, int row) {
        return "window|switch|" + caption + "|#collection=" + row + ",0";
    }
    public static void main(String[] args) {
        check(-1, key("old", 2), new String[]{key("new", 2)}, true);
        check(-1, key("same", 2), new String[]{key("same", 3), key("same", 4)}, true, false);
        check(1, key("same", 2), new String[]{key("same", 3), key("same", 2)}, true, false);
        check(0, key("SSID", 2), new String[]{key("SSID", 3), key("other", 2)}, false, true);
        check(-1, key("SSID", 2), new String[]{key("other", 2)}, true);
        check(-1, key("same", 2), new String[]{"other-window|switch|same|#collection=2,0"}, false);
        check(0, key("same", 2), new String[]{key("same", 2)}, true);
        System.out.println("PASS: " + checks + " recycled control identity cases");
    }
}
