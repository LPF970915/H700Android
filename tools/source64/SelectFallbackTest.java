package com.roc.rgsp.navtrial;

public final class SelectFallbackTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    public static void main(String[] args) {
        MouseHotkey h = new MouseHotkey();
        check(MouseHotkey.canonicalKey(82,310,false)==109);
        check(MouseHotkey.canonicalKey(82,312,false)==82);
        h.update(2,109,true,false,0);
        h.update(2,MouseHotkey.canonicalKey(82,310,false),true,false,1);
        check(h.update(2,109,false,false,2500));
        check(!h.update(2,109,false,false,2501));
        h.update(2,108,true,false,3000);
        h.update(2,109,true,false,3100);
        h.update(2,108,false,false,3200);
        check(!h.update(2,109,false,false,6000));
        h.update(2,109,true,false,7000);
        check(h.update(2,109,false,false,9500));
    }
}
