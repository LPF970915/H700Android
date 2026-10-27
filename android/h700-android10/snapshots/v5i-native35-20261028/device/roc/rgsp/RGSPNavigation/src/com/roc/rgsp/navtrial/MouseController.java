package com.roc.rgsp.navtrial;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.app.KeyguardManager;
import android.graphics.Path;
import android.os.Handler;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.WindowManager;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.Map;

/** Opt-in single-touch test mode. No network, root shell, or text-input logging. */
final class MouseController {
    interface Surface {
        void show(float x, float y, boolean pressed);
        void capture(boolean capture);
        void ended();
    }

    private final AccessibilityService service;
    private final Handler handler;
    private final WindowManager windows;
    private final Surface surface;
    private final PointerPosition point = new PointerPosition();
    // Retain consumed downs through mode transitions so their ups never leak.
    private final Map<Long, Integer> consumed = new HashMap<>();
    private boolean active, busy, destroyed, aLong;
    private Long selectKey, aKey;
    private float hatX, hatY, density = 1;
    private long movementStart, frameAt, geometryAt;
    private int generation, taps, longPresses, completed, cancelled, rejected, hatEvents;
    private String lastResult = "none";
    private final Runnable selectTimer = () -> {
        if (selectKey != null && allowed()) {
            if (active) exit(); else enter();
        }
    };
    private final Runnable aTimer = () -> {
        if (aKey != null && active && !busy) {
            aLong = true;
            touch(true);
        }
    };
    private final Runnable frame = new Runnable() {
        @Override public void run() {
            if (!active || destroyed) return;
            long now = SystemClock.uptimeMillis();
            if (now - geometryAt >= 200) {
                geometryAt = now;
                if (!allowed()) { exit(); return; }
                updateGeometry();
            }
            float dx = hatX, dy = hatY;
            for (int key : consumed.values()) {
                if (key == KeyEvent.KEYCODE_DPAD_LEFT) dx -= 1;
                if (key == KeyEvent.KEYCODE_DPAD_RIGHT) dx += 1;
                if (key == KeyEvent.KEYCODE_DPAD_UP) dy -= 1;
                if (key == KeyEvent.KEYCODE_DPAD_DOWN) dy += 1;
            }
            double length = Math.hypot(dx, dy);
            if (!busy && aKey == null && length > 0) {
                if (movementStart == 0) movementStart = now;
                // Bound each step after a slow frame; normalize diagonals.
                float speed = (now - movementStart < 500 ? 110 : 300) * density;
                float step = speed * Math.min(32, now - frameAt) / 1000f;
                point.move((float) (dx / length) * step, (float) (dy / length) * step);
                // A lost HAT release must not move indefinitely.
                if (now - movementStart > 10000) clearMovement();
            } else {
                movementStart = 0;
            }
            frameAt = now;
            surface.show(point.x, point.y, aKey != null || busy);
            handler.postDelayed(this, 16);
        }
    };

    MouseController(AccessibilityService service, Handler handler,
                    WindowManager windows, Surface surface) {
        this.service = service;
        this.handler = handler;
        this.windows = windows;
        this.surface = surface;
        updateGeometry();
    }

    boolean isActive() { return active; }

    private boolean allowed() {
        return !destroyed
                && ((PowerManager) service.getSystemService(AccessibilityService.POWER_SERVICE))
                    .isInteractive()
                && !((KeyguardManager) service.getSystemService(AccessibilityService.KEYGUARD_SERVICE))
                    .isKeyguardLocked();
    }

    private void updateGeometry() {
        DisplayMetrics metrics = new DisplayMetrics();
        windows.getDefaultDisplay().getRealMetrics(metrics);
        if (metrics.widthPixels != point.width || metrics.heightPixels != point.height) {
            point.resize(metrics.widthPixels, metrics.heightPixels);
            clearMovement();
            if (active && busy) exit();
        }
        density = Math.max(0.5f, metrics.density);
    }

    private void enter() {
        if (!allowed() || busy) return;
        updateGeometry();
        active = true;
        clearMovement();
        surface.capture(true);
        surface.show(point.x, point.y, false);
        frameAt = SystemClock.uptimeMillis();
        handler.removeCallbacks(frame);
        handler.post(frame);
    }

    void exit() {
        boolean wasActive = active;
        active = false;
        generation++;
        busy = false;
        aKey = null;
        handler.removeCallbacks(aTimer);
        handler.removeCallbacks(selectTimer);
        handler.removeCallbacks(frame);
        clearMovement();
        surface.show(-1, -1, false);
        if (wasActive) surface.ended();
    }

    void destroy() {
        destroyed = true;
        exit();
        consumed.clear();
    }

    private void clearMovement() {
        hatX = hatY = 0;
        movementStart = 0;
        consumed.entrySet().removeIf(entry -> direction(entry.getValue()));
    }

    private static boolean direction(int key) {
        return key >= KeyEvent.KEYCODE_DPAD_UP && key <= KeyEvent.KEYCODE_DPAD_RIGHT;
    }

    private static boolean confirm(KeyEvent event) {
        return event.getKeyCode() == KeyEvent.KEYCODE_BUTTON_A
                || event.getKeyCode() == KeyEvent.KEYCODE_DPAD_CENTER
                || (event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && (event.getScanCode() == 304 || event.getDeviceId() == -1));
    }

    boolean onKey(KeyEvent event) {
        int key = event.getKeyCode();
        long identity = ((long) event.getDeviceId() << 32) | key;
        boolean up = event.getAction() == KeyEvent.ACTION_UP;
        boolean owned = consumed.containsKey(identity);
        if (!allowed()) {
            if (active) exit();
            handler.removeCallbacks(selectTimer);
            handler.removeCallbacks(aTimer);
            selectKey = aKey = null;
            if (up && owned) consumed.remove(identity);
            return owned;
        }
        if (key == KeyEvent.KEYCODE_BUTTON_SELECT) {
            // Trial reserves Select, including short presses. Replaying delayed
            // keys needs a separate trusted injector, not malformed down/up pairs.
            if (!up && event.getAction() == KeyEvent.ACTION_DOWN && !owned) {
                consumed.put(identity, key);
                selectKey = identity;
                handler.postDelayed(selectTimer, 600);
            } else if (up && owned) {
                consumed.remove(identity);
                handler.removeCallbacks(selectTimer);
                selectKey = null;
            }
            return true;
        }
        if (up && owned) {
            consumed.remove(identity);
            if (aKey != null && aKey.longValue() == identity) {
                handler.removeCallbacks(aTimer);
                aKey = null;
                if (active && !busy && !aLong && !event.isCanceled()) touch(false);
            }
            return true;
        }
        if (!active) return owned;
        if (key == KeyEvent.KEYCODE_BACK || key == KeyEvent.KEYCODE_BUTTON_B
                || key == KeyEvent.KEYCODE_ESCAPE) {
            if (!up && event.getAction() == KeyEvent.ACTION_DOWN) {
                consumed.put(identity, key);
                exit();
            }
            return true;
        }
        if (confirm(event) || direction(key)) {
            if (!up && event.getAction() == KeyEvent.ACTION_DOWN && !owned) {
                consumed.put(identity, direction(key) && busy ? 0 : key);
                if (confirm(event) && aKey == null && !busy) {
                    aKey = identity;
                    aLong = false;
                    clearMovement();
                    handler.postDelayed(aTimer, 600);
                }
            }
            return true;
        }
        return false;
    }

    boolean onMotion(MotionEvent event) {
        if (!active || !event.isFromSource(InputDevice.SOURCE_JOYSTICK)) return false;
        if (event.getActionMasked() != MotionEvent.ACTION_MOVE) return false;
        hatEvents++;
        if (!busy && aKey == null) {
            float x = event.getAxisValue(MotionEvent.AXIS_HAT_X);
            float y = event.getAxisValue(MotionEvent.AXIS_HAT_Y);
            hatX = Math.abs(x) > 0.5f ? Math.signum(x) : 0;
            hatY = Math.abs(y) > 0.5f ? Math.signum(y) : 0;
        }
        return true;
    }

    private void touch(boolean longPress) {
        if (!active || busy || !allowed()) return;
        busy = true;
        clearMovement();
        surface.capture(false);
        final float x = point.x, y = point.y;
        final int token = ++generation;
        if (longPress) longPresses++; else taps++;
        lastResult = "pending";
        // Let WindowManager release key focus before the real touch is injected.
        handler.postDelayed(() -> {
            if (!active || token != generation || !allowed()) {
                if (token == generation) exit();
                return;
            }
            Path path = new Path();
            path.moveTo(x, y);
            GestureDescription gesture = new GestureDescription.Builder()
                    .addStroke(new GestureDescription.StrokeDescription(path, 0,
                            longPress ? 800 : 60)).build();
            try {
                boolean accepted = service.dispatchGesture(gesture,
                        new AccessibilityService.GestureResultCallback() {
                    @Override public void onCompleted(GestureDescription g) {
                        completed++;
                        finish(token, "completed");
                    }
                    @Override public void onCancelled(GestureDescription g) {
                        cancelled++;
                        finish(token, "cancelled");
                    }
                }, handler);
                if (!accepted) {
                    rejected++;
                    finish(token, "rejected");
                }
            } catch (RuntimeException error) {
                rejected++;
                finish(token, error.getClass().getSimpleName());
            }
        }, 80);
        handler.postDelayed(() -> {
            if (busy && token == generation) {
                lastResult = "timeout";
                exit();
            }
        }, 2500);
    }

    private void finish(int token, String result) {
        if (token != generation) return;
        lastResult = result;
        busy = false;
        if (active && allowed()) surface.capture(true);
        else exit();
    }

    void dump(PrintWriter writer) {
        writer.println("mouseMode=" + active + " cursor=" + point.x + "," + point.y
                + " display=" + point.width + "x" + point.height
                + " gestureBusy=" + busy + " lastGesture=" + lastResult
                + " taps=" + taps + " longPresses=" + longPresses
                + " completed=" + completed + " cancelled=" + cancelled
                + " rejected=" + rejected + " hatEvents=" + hatEvents);
    }
}
