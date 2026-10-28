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

/** Controller-operated single-touch pointer. No root or key-event reinjection. */
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
    private final MouseHotkey hotkey = new MouseHotkey();
    // Retain consumed downs through mode transitions so their ups never leak.
    private final Map<Long, Integer> consumed = new HashMap<>();
    private boolean active, busy, destroyed, aLong;
    private Long aKey, dragKey, scrollKey;
    private boolean dragRunning, dragEndRequested, scrollAxisArmed = true;
    private GestureDescription.StrokeDescription dragStroke;
    private float dragX, dragY;
    private int dragToken, drags, swipes;
    private long dragStarted;
    private float hatX, hatY, stickX, stickY, density = 1;
    private long movementStart, frameAt, geometryAt;
    private int generation, taps, longPresses, completed, cancelled, rejected, hatEvents, stickEvents;
    private String lastResult = "none";
    private final Runnable dragWatchdog = () -> stopDrag();
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
            float dx = 0, dy = 0;
            for (int key : consumed.values()) {
                if (key == KeyEvent.KEYCODE_DPAD_LEFT) dx -= 1;
                if (key == KeyEvent.KEYCODE_DPAD_RIGHT) dx += 1;
                if (key == KeyEvent.KEYCODE_DPAD_UP) dy -= 1;
                if (key == KeyEvent.KEYCODE_DPAD_DOWN) dy += 1;
            }
            if (dx == 0 && dy == 0) { dx = hatX; dy = hatY; }
            if (dx == 0 && dy == 0) { dx = stickX; dy = stickY; }
            double length = Math.hypot(dx, dy);
            if ((!busy || dragRunning) && aKey == null && scrollKey == null && length > 0) {
                if (movementStart == 0) movementStart = now;
                // Bound each step after a slow frame; normalize diagonals.
                float speed = (now - movementStart < 500 ? 110 : 300) * density;
                float step = speed * Math.min(32, now - frameAt) / 1000f;
                point.move(StickVector.bounded(dx, dx, dy) * step,
                        StickVector.bounded(dy, dx, dy) * step);
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
        if (dragRunning) stopDrag();
        else busy = false;
        aKey = null;
        dragKey = scrollKey = null;
        handler.removeCallbacks(aTimer);
        handler.removeCallbacks(frame);
        clearMovement();
        surface.show(-1, -1, false);
        if (wasActive) surface.ended();
    }

    void destroy() {
        destroyed = true;
        exit();
        hotkey.clear();
        consumed.clear();
    }

    private void clearMovement() {
        hatX = hatY = 0;
        stickX = stickY = 0;
        movementStart = 0;
        // Stop motion without losing ownership of a down already consumed.
        // Its eventual up must never leak to an application after mode exit.
        for (Map.Entry<Long, Integer> entry : consumed.entrySet())
            if (direction(entry.getValue())) entry.setValue(0);
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
            hotkey.clear();
            handler.removeCallbacks(aTimer);
            aKey = null;
            if (up && owned) consumed.remove(identity);
            return owned;
        }
        boolean toggle = hotkey.update(event.getDeviceId(), key,
                event.getAction() == KeyEvent.ACTION_DOWN, event.isCanceled());
        if (toggle) {
            consumed.put(identity, key);
            if (active) exit(); else enter();
            return true;
        }
        // Unmodified Select, Start and shoulder pairs retain their original
        // timing and events. Only the recognized chord owns its Start pair.
        if (up && owned) {
            consumed.remove(identity);
            if (direction(key)) scrollAxisArmed = true;
            if (dragKey != null && dragKey.longValue() == identity) {
                dragKey = null; stopDrag();
            }
            if (scrollKey != null && scrollKey.longValue() == identity) {
                scrollKey = null; clearMovement(); scrollAxisArmed = true;
            }
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
        if (key == KeyEvent.KEYCODE_BUTTON_X || key == KeyEvent.KEYCODE_BUTTON_Y) {
            if (!up && event.getAction() == KeyEvent.ACTION_DOWN && !owned) {
                consumed.put(identity, key);
                if (!busy && aKey == null) {
                    if (key == KeyEvent.KEYCODE_BUTTON_X) {
                        dragKey = identity; startDrag();
                    } else {
                        scrollKey = identity; scrollAxisArmed = true; clearMovement();
                    }
                }
            }
            return true;
        }
        if (confirm(event) || direction(key)) {
            if (!up && event.getAction() == KeyEvent.ACTION_DOWN && !owned) {
                consumed.put(identity, direction(key) && ((busy && !dragRunning) || scrollKey != null) ? 0 : key);
                if (direction(key) && scrollKey != null && !busy && scrollAxisArmed) {
                    scrollAxisArmed = false; swipe(key);
                }
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
        if (event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
            clearMovement(); return true;
        }
        if (event.getActionMasked() != MotionEvent.ACTION_MOVE) return false;
        hatEvents++;
        if ((!busy || dragRunning) && aKey == null) {
            float x = event.getAxisValue(MotionEvent.AXIS_HAT_X);
            float y = event.getAxisValue(MotionEvent.AXIS_HAT_Y);
            hatX = Math.abs(x) > 0.5f ? Math.signum(x) : 0;
            hatY = Math.abs(y) > 0.5f ? Math.signum(y) : 0;
            float[] stick = sticks(event);
            stickX = stick[0]; stickY = stick[1];
            if (stickX != 0 || stickY != 0) stickEvents++;
            if (scrollKey != null) {
                float sx = hatX != 0 ? hatX : stickX, sy = hatY != 0 ? hatY : stickY;
                if (Math.max(Math.abs(sx), Math.abs(sy)) < 0.4f) scrollAxisArmed = true;
                else if (scrollAxisArmed && !busy && Math.max(Math.abs(sx), Math.abs(sy)) > 0.6f) {
                    scrollAxisArmed = false;
                    swipe(Math.abs(sx) > Math.abs(sy)
                            ? (sx > 0 ? KeyEvent.KEYCODE_DPAD_RIGHT : KeyEvent.KEYCODE_DPAD_LEFT)
                            : (sy > 0 ? KeyEvent.KEYCODE_DPAD_DOWN : KeyEvent.KEYCODE_DPAD_UP));
                }
            }
        }
        return true;
    }

    static float axis(MotionEvent event, int axis) {
        InputDevice device = event.getDevice();
        InputDevice.MotionRange range = device == null ? null : device.getMotionRange(axis, event.getSource());
        return range == null ? 0 : StickVector.centered(event.getAxisValue(axis), range.getFlat());
    }

    static float[] sticks(MotionEvent event) {
        float x = axis(event, MotionEvent.AXIS_X), y = axis(event, MotionEvent.AXIS_Y);
        InputDevice device = event.getDevice();
        boolean zr = device != null && device.getMotionRange(MotionEvent.AXIS_Z, event.getSource()) != null
                && device.getMotionRange(MotionEvent.AXIS_RZ, event.getSource()) != null;
        float rx = axis(event, zr ? MotionEvent.AXIS_Z : MotionEvent.AXIS_RX);
        float ry = axis(event, zr ? MotionEvent.AXIS_RZ : MotionEvent.AXIS_RY);
        return rx * rx + ry * ry > x * x + y * y ? new float[]{rx, ry} : new float[]{x, y};
    }

    private void touch(boolean longPress) {
        if (!active || busy || !allowed()) return;
        Path path = new Path(); path.moveTo(point.x, point.y);
        if (longPress) longPresses++; else taps++;
        gesture(path, longPress ? 800 : 60);
    }

    private void swipe(int key) {
        if (!active || busy || !allowed()) return;
        boolean vertical = key == KeyEvent.KEYCODE_DPAD_UP || key == KeyEvent.KEYCODE_DPAD_DOWN;
        float radius = Math.min(180, (vertical ? point.height : point.width) * 0.23f);
        float sign = key == KeyEvent.KEYCODE_DPAD_DOWN || key == KeyEvent.KEYCODE_DPAD_RIGHT ? 1 : -1;
        float startX = point.x, endX = point.x, startY = point.y, endY = point.y;
        if (vertical) {
            startY = Math.max(4, Math.min(point.height - 5, point.y + sign * radius));
            endY = Math.max(4, Math.min(point.height - 5, point.y - sign * radius));
        } else {
            startX = Math.max(4, Math.min(point.width - 5, point.x + sign * radius));
            endX = Math.max(4, Math.min(point.width - 5, point.x - sign * radius));
        }
        if (Math.hypot(endX - startX, endY - startY) < 8) return;
        Path path = new Path(); path.moveTo(startX, startY); path.lineTo(endX, endY);
        swipes++; gesture(path, 320);
    }

    private void gesture(Path path, long duration) {
        busy = true; clearMovement(); surface.capture(false);
        final int token = ++generation;
        lastResult = "pending";
        // Let WindowManager release key focus before the real touch is injected.
        handler.postDelayed(() -> {
            if (!active || token != generation || !allowed()) {
                if (token == generation) exit();
                return;
            }
            GestureDescription gesture = new GestureDescription.Builder()
                    .addStroke(new GestureDescription.StrokeDescription(path, 0, duration)).build();
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

    private void startDrag() {
        if (!active || busy || !allowed()) return;
        generation++; // Retire any completed tap/long-press timeout.
        busy = dragRunning = true; dragEndRequested = false; dragStroke = null;
        clearMovement(); dragX = Math.round(point.x); dragY = Math.round(point.y);
        dragStarted = SystemClock.uptimeMillis();
        int token = ++dragToken; drags++; surface.capture(false);
        handler.postDelayed(() -> dragSegment(token), 80);
        handler.postDelayed(dragWatchdog, 30000);
    }

    private void stopDrag() {
        dragEndRequested = true;
        if (dragRunning && dragStroke != null && dragStroke.willContinue()) {
            // Queue the final UP behind the scheduled segment. Older callbacks
            // lose ownership so they cannot append another continuation.
            int token = ++dragToken;
            handler.post(() -> dragSegment(token));
        }
    }

    private void dragSegment(int token) {
        if (token != dragToken || !dragRunning) return;
        if (!allowed() && dragStroke == null) { finishDrag("cancelled"); return; }
        boolean continuing = active && allowed() && !dragEndRequested
                && SystemClock.uptimeMillis() - dragStarted < 30000;
        float endX = active ? Math.round(point.x) : dragX;
        float endY = active ? Math.round(point.y) : dragY;
        // Android 10 rejects a stationary continuation with willContinue=true:
        // it generates no MotionEvents, reports cancellation, and leaves the
        // previous contact open. Wait for a moved pixel or the final UP instead.
        if (dragStroke != null && continuing && endX == dragX && endY == dragY) {
            handler.postDelayed(() -> dragSegment(token), 40);
            return;
        }
        Path path = new Path(); path.moveTo(dragX, dragY);
        if (endX != dragX || endY != dragY) path.lineTo(endX, endY);
        try {
            GestureDescription.StrokeDescription stroke = dragStroke == null
                    ? new GestureDescription.StrokeDescription(path, 0, 80, continuing)
                    : dragStroke.continueStroke(path, 0, 80, continuing);
            dragStroke = stroke; dragX = endX; dragY = endY;
            GestureDescription gesture = new GestureDescription.Builder().addStroke(stroke).build();
            boolean accepted = service.dispatchGesture(gesture, new AccessibilityService.GestureResultCallback() {
                @Override public void onCompleted(GestureDescription g) {
                    if (token != dragToken || !dragRunning) return;
                    if (continuing) {
                        if (active && allowed()) surface.capture(true);
                        handler.post(() -> dragSegment(token));
                    } else finishDrag("completed");
                }
                @Override public void onCancelled(GestureDescription g) {
                    if (token == dragToken && dragRunning) finishDrag("cancelled");
                }
            }, handler);
            if (!accepted) finishDrag("rejected");
        } catch (RuntimeException failure) { finishDrag(failure.getClass().getSimpleName()); }
    }

    private void finishDrag(String result) {
        handler.removeCallbacks(dragWatchdog);
        dragRunning = busy = false; dragStroke = null; dragKey = null;
        lastResult = "drag-" + result;
        if ("completed".equals(result)) completed++;
        else if ("cancelled".equals(result)) cancelled++;
        else rejected++;
        clearMovement();
        if (active && allowed()) surface.capture(true);
    }

    private void finish(int token, String result) {
        if (token != generation) return;
        lastResult = result;
        busy = false;
        scrollAxisArmed = true;
        if (active && allowed()) surface.capture(true);
        else exit();
    }

    void dump(PrintWriter writer) {
        writer.println("mouseMode=" + active + " cursor=" + point.x + "," + point.y
                + " display=" + point.width + "x" + point.height
                + " gestureBusy=" + busy + " lastGesture=" + lastResult
                + " taps=" + taps + " longPresses=" + longPresses
                + " completed=" + completed + " cancelled=" + cancelled
                + " rejected=" + rejected + " hatEvents=" + hatEvents
                + " stickEvents=" + stickEvents + " stick=" + stickX + "," + stickY);
        writer.println("mouseHotkey=L1+R1+Start drag=" + dragRunning + " drags=" + drags
                + " swipes=" + swipes + " scrollHeld=" + (scrollKey != null));
    }
}
