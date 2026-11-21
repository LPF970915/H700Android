package com.roc.rgsp.gamepadcheck;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.os.Bundle;
import android.util.Log;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import java.util.Locale;

/** Displays the input this foreground Android app actually receives. */
public final class GamepadCheck extends Activity {
    private static final String TAG = "ROCGamepadCheck";
    private static final int[] KEYS = {96, 97, 99, 100, 102, 103, 104, 105,
            109, 108, 106, 107, 110, 25, 24};
    private static final String[] LABELS = {"A", "B", "X", "Y", "L1", "R1", "L2", "R2",
            "SELECT", "START", "L3", "R3", "MODE", "VOL−", "VOL+"};
    private static final int[] AXES = {MotionEvent.AXIS_HAT_X, MotionEvent.AXIS_HAT_Y,
            MotionEvent.AXIS_X, MotionEvent.AXIS_Y, MotionEvent.AXIS_Z, MotionEvent.AXIS_RZ,
            MotionEvent.AXIS_LTRIGGER, MotionEvent.AXIS_RTRIGGER};
    private static final String[] AXIS_NAMES = {"HAT X", "HAT Y", "左 X", "左 Y", "右 Z", "右 RZ",
            "L2 轴", "R2 轴"};
    private final int[] downs = new int[KEYS.length], ups = new int[KEYS.length];
    private final int[] scans = new int[KEYS.length], activeDevice = new int[KEYS.length];
    private final boolean[] held = new boolean[KEYS.length];
    private final float[] values = new float[AXES.length], minimum = new float[AXES.length],
            maximum = new float[AXES.length];
    private final boolean[] hasAxis = new boolean[AXES.length];
    private int confirmations;
    private String lastInput = "等待输入";
    private Panel panel;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        panel = new Panel();
        setContentView(panel);
        Log.i(TAG, "READY");
    }

    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode(), scan = event.getScanCode();
        int action = event.getAction();
        if (action != KeyEvent.ACTION_DOWN && action != KeyEvent.ACTION_UP) {
            return super.dispatchKeyEvent(event);
        }
        for (int i = 0; i < KEYS.length; i++) {
            if (KEYS[i] != code) continue;
            if (action == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                downs[i]++;
                activeDevice[i] = event.getDeviceId();
                held[i] = true;
            } else if (action == KeyEvent.ACTION_UP) {
                if (held[i] && activeDevice[i] == event.getDeviceId() && !event.isCanceled()) {
                    ups[i]++;
                    if (code == KeyEvent.KEYCODE_BUTTON_A) confirmations++;
                }
                held[i] = false;
            }
            scans[i] = scan;
            describe(event);
            return true;
        }
        if (code == KeyEvent.KEYCODE_ENTER || code == KeyEvent.KEYCODE_DPAD_CENTER
                || (code >= KeyEvent.KEYCODE_DPAD_UP && code <= KeyEvent.KEYCODE_DPAD_RIGHT)) {
            describe(event);
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    private void describe(KeyEvent event) {
        String edge = event.getAction() == KeyEvent.ACTION_DOWN ? "DOWN" : "UP";
        lastInput = KeyEvent.keyCodeToString(event.getKeyCode()) + "  " + event.getKeyCode()
                + "   scan " + event.getScanCode() + "   " + edge;
        Log.i(TAG, "KEY code=" + event.getKeyCode() + " scan=" + event.getScanCode()
                + " edge=" + edge + " source=" + Integer.toHexString(event.getSource())
                + " device=" + event.getDeviceId() + " repeat=" + event.getRepeatCount()
                + " canceled=" + event.isCanceled() + " A_confirm=" + confirmations);
        panel.invalidate();
    }

    @Override public boolean dispatchGenericMotionEvent(MotionEvent event) {
        if (!event.isFromSource(InputDevice.SOURCE_JOYSTICK)
                || event.getActionMasked() != MotionEvent.ACTION_MOVE || event.getDevice() == null) {
            return super.dispatchGenericMotionEvent(event);
        }
        for (int i = 0; i < AXES.length; i++) {
            if (event.getDevice().getMotionRange(AXES[i], InputDevice.SOURCE_JOYSTICK) == null) continue;
            hasAxis[i] = true;
            for (int h = 0; h < event.getHistorySize(); h++) {
                sample(i, event.getHistoricalAxisValue(AXES[i], h));
            }
            sample(i, event.getAxisValue(AXES[i]));
        }
        panel.invalidate();
        return true;
    }

    private void sample(int i, float value) {
        int axis = AXES[i];
        boolean reportEdges = i < 2 || axis == MotionEvent.AXIS_LTRIGGER
                || axis == MotionEvent.AXIS_RTRIGGER;
        if ((reportEdges && Math.abs(values[i] - value) > 0.05f)
                || value < minimum[i] - 0.05f || value > maximum[i] + 0.05f) {
            Log.i(TAG, "AXIS " + MotionEvent.axisToString(axis) + " value=" + value);
        }
        values[i] = value;
        minimum[i] = Math.min(minimum[i], value);
        maximum[i] = Math.max(maximum[i], value);
    }

    private final class Panel extends View {
        final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        final int ink = 0xffeff6f4, quiet = 0xff9cb4b6, cyan = 0xff7de5ca;

        Panel() { super(GamepadCheck.this); }

        void text(Canvas canvas, String value, float x, float y, float size, int color) {
            paint.setColor(color);
            paint.setTextSize(size);
            canvas.drawText(value, x, y, paint);
        }

        @Override public void onDraw(Canvas canvas) {
            canvas.drawColor(0xff101a21);
            canvas.save();
            canvas.scale(getWidth() / 720f, getHeight() / 480f);
            text(canvas, "手柄按键检测", 22, 37, 28, ink);
            text(canvas, "A 确认  " + confirmations, 518, 36, 23, cyan);
            text(canvas, "短按每个实体键，松开后计数应成对。转动摇杆并松手查看回中。", 22, 65, 15, quiet);
            text(canvas, lastInput, 22, 94, 18, cyan);
            for (int i = 0; i < LABELS.length; i++) {
                int x = 22 + (i % 5) * 136, y = 111 + (i / 5) * 61;
                paint.setColor(held[i] ? 0xff246958 : ups[i] > 0 ? 0xff213e42 : 0xff1b2a33);
                canvas.drawRoundRect(x, y, x + 127, y + 52, 8, 8, paint);
                text(canvas, LABELS[i], x + 8, y + 22, 17, ink);
                String state = downs[i] + "↓ / " + ups[i] + "↑";
                if (scans[i] != 0) state += " · " + scans[i];
                text(canvas, state, x + 8, y + 41, 13, quiet);
            }
            for (int i = 0; i < AXES.length; i++) {
                int x = 22 + (i % 2) * 342, y = 317 + (i / 2) * 34;
                String current = hasAxis[i] ? String.format(Locale.ROOT, "% .2f   [% .2f, % .2f]",
                        values[i], minimum[i], maximum[i]) : "等待轴事件";
                text(canvas, AXIS_NAMES[i], x, y, 16, cyan);
                text(canvas, current, x + 83, y, 16, ink);
            }
            text(canvas, "轴  当前值 [最小值, 最大值]    系统接管的快捷键可能不送到本页。", 22, 454, 15, quiet);
            canvas.restore();
        }
    }
}
