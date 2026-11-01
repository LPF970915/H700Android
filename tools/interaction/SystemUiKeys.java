package com.roc.h700.parity;

import android.app.Dialog;
import android.os.Build;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import java.util.ArrayList;
import java.util.List;
import java.util.WeakHashMap;

/** Native SystemUI equivalent of the frozen controller-only power menu policy. */
public final class SystemUiKeys {
    private static final WeakHashMap<Dialog,Integer> hats = new WeakHashMap<>();

    public static boolean physicalA(KeyEvent event) {
        return "rgsp".equals(Build.DEVICE) && event.getKeyCode()==KeyEvent.KEYCODE_ENTER
                && event.getScanCode()==304 && event.getDevice()!=null
                && "ANBERNIC-keys".equals(event.getDevice().getName());
    }

    private static boolean applies(Dialog dialog) {
        return "rgsp".equals(Build.DEVICE) && dialog.getWindow()!=null;
    }

    private static void collect(View view, List<View> items) {
        if(view.getVisibility()!=View.VISIBLE || !view.isEnabled()) return;
        if(view.isClickable() && view.findViewById(android.R.id.message)!=null) {
            // The actual action row has exactly one label. The outer layout
            // and dismiss scrim contain several actions and are not targets.
            if(countLabels(view)==1) {items.add(view);return;}
        }
        if(view instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++) collect(group.getChildAt(i),items);
        }
    }

    private static int countLabels(View view) {
        int result=view.getId()==android.R.id.message ? 1 : 0;
        if(view instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++) result+=countLabels(group.getChildAt(i));
        }
        return result;
    }

    private static void move(Dialog dialog,int delta) {
        List<View> items=new ArrayList<>();
        collect(dialog.getWindow().getDecorView(),items);
        if(items.isEmpty()) return;
        int current=-1;
        for(int i=0;i<items.size();i++) {
            View item=items.get(i);
            item.setFocusable(true);item.setFocusableInTouchMode(true);
            if(item.hasFocus()) current=i;
        }
        int target=current<0 ? 0 : Math.max(0,Math.min(items.size()-1,current+delta));
        items.get(target).requestFocus();
    }

    public static void start(Dialog dialog) {
        if(!applies(dialog)) return;
        hats.remove(dialog);
        dialog.getWindow().getDecorView().post(() -> move(dialog,0));
    }

    public static boolean key(Dialog dialog,KeyEvent event) {
        if(!applies(dialog)) return false;
        int key=event.getKeyCode();
        if(key<KeyEvent.KEYCODE_DPAD_UP || key>KeyEvent.KEYCODE_DPAD_RIGHT) return false;
        if(event.getAction()==KeyEvent.ACTION_DOWN) move(dialog,
                key==KeyEvent.KEYCODE_DPAD_UP || key==KeyEvent.KEYCODE_DPAD_LEFT ? -1 : 1);
        return true;
    }

    public static boolean motion(Dialog dialog,MotionEvent event) {
        if(!applies(dialog) || event.getDevice()==null
                || !"ANBERNIC-keys".equals(event.getDevice().getName())
                || (event.getSource() & InputDevice.SOURCE_CLASS_JOYSTICK)==0) return false;
        if(event.getActionMasked()==MotionEvent.ACTION_CANCEL) {hats.remove(dialog);return true;}
        if(event.getActionMasked()!=MotionEvent.ACTION_MOVE) return false;
        float x=event.getAxisValue(MotionEvent.AXIS_HAT_X),y=event.getAxisValue(MotionEvent.AXIS_HAT_Y);
        int direction=Math.abs(y)>.5f ? (y<0 ? -1 : 1) : Math.abs(x)>.5f ? (x<0 ? -1 : 1) : 0;
        Integer previous=hats.get(dialog);
        if(direction!=0 && (previous==null || previous!=direction)) move(dialog,direction);
        hats.put(dialog,direction);
        return true;
    }
}
