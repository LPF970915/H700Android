package com.roc.rgsp.navtrial;

public final class MenuHotkeyTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static int key(MenuHotkey h, int device, int key, boolean down, long time) {
        return h.update(device, key, 0, false, down, false, time);
    }
    public static void main(String[] args) {
        MenuHotkey h = new MenuHotkey();
        check(!MenuHotkey.isMenu(82,310,true));
        check(MenuHotkey.isMenu(3,312,true));
        check(!MenuHotkey.isMenu(3,312,false));
        check(key(h,1,110,true,0)==MenuHotkey.CONSUME);
        check(h.nextDelay(0)==700 && !h.fireLong(699));
        check(key(h,1,110,false,699)==MenuHotkey.HOME);
        check(key(h,1,110,false,700)==MenuHotkey.CONSUME);
        key(h,1,110,true,1000); key(h,1,110,true,1200);
        check(h.nextDelay(1200)==500 && h.fireLong(1700));
        check(!h.fireLong(1701) && h.nextDelay(1701)==-1);
        check(key(h,1,110,false,1800)==MenuHotkey.CONSUME);
        key(h,1,110,true,2000);
        check(key(h,1,110,false,2700)==MenuHotkey.QUICK_SETTINGS);
        key(h,1,110,true,3000); key(h,1,108,true,3100); key(h,1,108,false,3200);
        check(!h.fireLong(4000) && key(h,1,110,false,4100)==MenuHotkey.CONSUME);
        key(h,1,109,true,5000); key(h,1,110,true,5100); key(h,1,109,false,5200);
        check(!h.fireLong(6000) && key(h,1,110,false,6100)==MenuHotkey.CONSUME);
        key(h,1,110,true,7000); key(h,2,108,true,7100);
        check(h.fireLong(7700)); key(h,1,110,false,7800); h.clear();
        h.update(1,110,0,false,true,true,8000);
        check(!h.fireLong(9000) && key(h,1,110,false,9100)==MenuHotkey.CONSUME);
        key(h,1,110,true,10000); h.clear();
        check(!h.fireLong(11000) && key(h,1,110,false,11000)==MenuHotkey.CONSUME);
        key(h,1,110,true,12000); check(!h.fireLong(11999));
        check(h.nextDelay(11999)==700);
        check(key(h,1,82,true,13000)==MenuHotkey.PASS);
        System.out.println("MenuHotkeyTest PASS");
    }
}
