package com.roc.rgsp.inputprobe;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import org.json.JSONObject;

/** Disposable, no-permission input target. Records only its own controller/touch events. */
public final class PointerProbe extends Activity {
    private PrintWriter log;
    private int downs, ups, cancels, moves;
    private float firstX, firstY, lastX, lastY;
    private long downAt;
    private boolean touching;
    private String lastKey = "";
    private Surface surface;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try { log = new PrintWriter(new FileOutputStream(new File(getFilesDir(), "events.jsonl")), true); }
        catch (Exception failure) { throw new IllegalStateException(failure); }
        surface = new Surface(); setContentView(surface);
    }

    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        int key = event.getKeyCode();
        if ((key >= 96 && key <= 110) || (key >= 19 && key <= 23) || key == 66 || key == 4) {
            try {
                JSONObject value = new JSONObject(); value.put("type", "key");
                value.put("action", event.getAction()); value.put("key", key);
                value.put("device", event.getDeviceId()); value.put("scan", event.getScanCode());
                value.put("repeat", event.getRepeatCount()); value.put("downTime", event.getDownTime());
                value.put("time", event.getEventTime()); value.put("cancelled", event.isCanceled());
                log.println(value.toString());
            } catch (Exception failure) { throw new IllegalStateException(failure); }
            lastKey = key + "/" + event.getAction(); surface.invalidate(); return true;
        }
        return super.dispatchKeyEvent(event);
    }

    private final class Surface extends View {
        private final Paint paint = new Paint(3);
        Surface() { super(PointerProbe.this); setFocusableInTouchMode(true); requestFocus(); }
        @Override protected void onDraw(Canvas canvas) {
            canvas.drawColor(Color.rgb(19, 31, 42));
            paint.setColor(Color.WHITE); paint.setTextSize(22);
            canvas.drawText("H700 input fixture - own surface only", 24, 38, paint);
            canvas.drawText("DOWN " + downs + "  UP " + ups + "  CANCEL " + cancels + "  key " + lastKey, 24, 72, paint);
            canvas.drawText("X hold: drag    Y + direction: scroll", 24, 106, paint);
            paint.setColor(touching ? Color.GREEN : Color.CYAN);
            canvas.drawCircle(lastX, lastY, 20, paint);
            paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(2);
            canvas.drawRect(30, 130, getWidth() - 30, getHeight() - 25, paint);
            paint.setStyle(Paint.Style.FILL);
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            int action = event.getActionMasked();
            if (action == MotionEvent.ACTION_DOWN) {
                downs++; touching = true; moves = 0;
                firstX = event.getX(); firstY = event.getY(); downAt = event.getEventTime();
            } else if (action == MotionEvent.ACTION_MOVE) moves++;
            lastX = event.getX(); lastY = event.getY();
            try {
                JSONObject value = new JSONObject(); value.put("type", "touch");
                value.put("action", action); value.put("time", event.getEventTime());
                value.put("x", lastX); value.put("y", lastY); value.put("pointers", event.getPointerCount());
                if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
                    touching = false;
                    if (action == MotionEvent.ACTION_UP) ups++; else cancels++;
                    value.put("duration", event.getEventTime() - downAt); value.put("moves", moves);
                    value.put("dx", lastX - firstX); value.put("dy", lastY - firstY);
                }
                log.println(value.toString());
            } catch (Exception failure) { throw new IllegalStateException(failure); }
            invalidate(); return true;
        }
    }

    @Override protected void onDestroy() { if (log != null) log.close(); super.onDestroy(); }
}
