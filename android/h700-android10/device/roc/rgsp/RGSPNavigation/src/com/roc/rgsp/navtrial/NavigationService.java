package com.roc.rgsp.navtrial;

import android.accessibilityservice.AccessibilityService;
import android.app.KeyguardManager;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.SparseBooleanArray;
import android.view.KeyEvent;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import java.io.FileDescriptor;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

public final class NavigationService extends AccessibilityService {
    private static final String SETTINGS = "com.android.settings";
    private static final String FILES = "com.android.documentsui";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final SparseBooleanArray held = new SparseBooleanArray();
    private final Runnable refreshTask = () -> refresh();
    private AccessibilityNodeInfo selected;
    private FocusRing ring;
    private WindowManager windows;
    private WindowManager.LayoutParams overlayParams;
    private long releaseUntil;
    private int moveTop;
    private String mode = "inactive";
    private int keyDownCount;
    private int navigationCallbacks;
    private String lastKeyScope = "none";
    private int actionCount;
    private boolean lastAction;

    @Override public void onServiceConnected() {
        if (!"rgsp".equals(Build.DEVICE)) {
            disableSelf();
            return;
        }
        try {
            Context settings = createPackageContext(SETTINGS, 0);
            moveTop = settings.getResources().getIdentifier(
                    "action_drag_move_top", "id", SETTINGS);
        } catch (Exception ignored) {
            moveTop = 0;
        }
        windows = (WindowManager) getSystemService(WINDOW_SERVICE);
        ring = new FocusRing(this);
        overlayParams = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        windows.addView(ring, overlayParams);
        refresh();
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        handler.removeCallbacks(refreshTask);
        handler.postDelayed(refreshTask, 100);
    }

    @Override public void onInterrupt() {
        clearSelection();
    }

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        clearSelection();
        if (windows != null && ring != null) windows.removeView(ring);
        super.onDestroy();
    }

    private boolean editorActive(AccessibilityNodeInfo root) {
        AccessibilityNodeInfo focus = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        boolean editable = focus != null && (focus.isEditable() || focus.isPassword());
        if (focus != null) focus.recycle();
        if (editable) return true;
        boolean keyboard = false;
        for (AccessibilityWindowInfo window : getWindows()) {
            keyboard |= window.getType() == AccessibilityWindowInfo.TYPE_INPUT_METHOD;
            window.recycle();
        }
        return keyboard;
    }

    private String scope(AccessibilityNodeInfo root) {
        if (root == null) return "inactive";
        String pkg = String.valueOf(root.getPackageName());
        if (!SETTINGS.equals(pkg) && !FILES.equals(pkg)) return "inactive";
        if (editorActive(root)) return "editor";
        if (FILES.equals(pkg)) return "files";
        List<AccessibilityNodeInfo> lists = root.findAccessibilityNodeInfosByViewId(
                SETTINGS + ":id/dragList");
        boolean found = false;
        for (AccessibilityNodeInfo list : lists) {
            found |= list.isVisibleToUser();
            list.recycle();
        }
        return found ? "locales" : "inactive";
    }

    private AccessibilityNodeInfo applicationRoot() {
        if (!((PowerManager) getSystemService(POWER_SERVICE)).isInteractive()
                || ((KeyguardManager) getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked()) {
            return null;
        }
        AccessibilityNodeInfo result = null;
        boolean systemFocused = false;
        for (AccessibilityWindowInfo window : getWindows()) {
            if (window.isFocused() && window.getType() == AccessibilityWindowInfo.TYPE_SYSTEM) {
                systemFocused = true;
            }
            if (result == null && window.getType() == AccessibilityWindowInfo.TYPE_APPLICATION) {
                result = window.getRoot();
            }
            window.recycle();
        }
        if (systemFocused && result != null) {
            result.recycle();
            return null;
        }
        return result;
    }

    private void overlayFocus(boolean focus) {
        if (ring == null) return;
        int flags = overlayParams.flags;
        if (focus) flags &= ~WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        else flags |= WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
        if (flags != overlayParams.flags) {
            overlayParams.flags = flags;
            windows.updateViewLayout(ring, overlayParams);
        }
        if (focus) ring.requestFocus();
        else ring.stopRepeat();
    }

    private void releaseForAction() {
        releaseUntil = SystemClock.uptimeMillis() + 500;
        overlayFocus(false);
    }

    private void back() {
        releaseForAction();
        clearSelection();
        handler.postDelayed(() -> performGlobalAction(GLOBAL_ACTION_BACK), 80);
        handler.postDelayed(refreshTask, 550);
    }

    private boolean localeRow(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo parent = node.getParent();
        boolean result = parent != null
                && (SETTINGS + ":id/dragList").equals(parent.getViewIdResourceName());
        if (parent != null) parent.recycle();
        return result;
    }

    private void collect(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> items) {
        if (!node.isVisibleToUser() || !node.isEnabled()) return;
        if (node.isPassword() || node.isEditable()) return;
        boolean row = "locales".equals(mode) && localeRow(node);
        boolean doc = (FILES + ":id/item_root").equals(node.getViewIdResourceName());
        if (row || doc || node.isClickable()) {
            Rect bounds = new Rect();
            node.getBoundsInScreen(bounds);
            if (!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
            return;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                collect(child, items);
                child.recycle();
            }
        }
    }

    private AccessibilityNodeInfo surface(AccessibilityNodeInfo root) {
        if ("files".equals(mode)) {
            List<AccessibilityNodeInfo> drawers = root.findAccessibilityNodeInfosByViewId(
                    FILES + ":id/drawer_roots");
            AccessibilityNodeInfo result = null;
            for (AccessibilityNodeInfo drawer : drawers) {
                Rect bounds = new Rect();
                drawer.getBoundsInScreen(bounds);
                if (result == null && drawer.isVisibleToUser()
                        && bounds.left >= 0 && bounds.width() > 100) {
                    result = AccessibilityNodeInfo.obtain(drawer);
                }
                drawer.recycle();
            }
            if (result != null) return result;
        }
        return AccessibilityNodeInfo.obtain(root);
    }

    private void collectItems(AccessibilityNodeInfo root, List<AccessibilityNodeInfo> items) {
        AccessibilityNodeInfo surface = surface(root);
        collect(surface, items);
        surface.recycle();
    }

    private void clearSelection() {
        if (selected != null) selected.recycle();
        selected = null;
        if (ring != null) ring.show(null);
        overlayFocus(false);
    }

    private void select(AccessibilityNodeInfo node) {
        boolean changed = selected == null || !selected.equals(node);
        if (selected != null) selected.recycle();
        selected = AccessibilityNodeInfo.obtain(node);
        if (changed) {
            node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        }
        Rect bounds = new Rect();
        node.getBoundsInScreen(bounds);
        if (ring != null) ring.show(bounds);
    }

    private int current(List<AccessibilityNodeInfo> items) {
        if (selected != null) {
            for (int i = 0; i < items.size(); i++) {
                if (selected.equals(items.get(i))) return i;
            }
        }
        return -1;
    }

    private int initial(List<AccessibilityNodeInfo> items) {
        if ("locales".equals(mode)) {
            for (int i = 0; i < items.size(); i++) {
                if (localeRow(items.get(i))) return i;
            }
        }
        return items.isEmpty() ? -1 : 0;
    }

    private void refresh() {
        if (SystemClock.uptimeMillis() < releaseUntil) {
            handler.removeCallbacks(refreshTask);
            handler.postDelayed(refreshTask, releaseUntil - SystemClock.uptimeMillis() + 20);
            return;
        }
        AccessibilityNodeInfo root = applicationRoot();
        mode = scope(root);
        if (!"locales".equals(mode) && !"files".equals(mode)) {
            clearSelection();
            if (root != null) root.recycle();
            return;
        }
        List<AccessibilityNodeInfo> items = new ArrayList<>();
        collectItems(root, items);
        int index = current(items);
        if (index < 0) index = initial(items);
        if (index >= 0) select(items.get(index)); else clearSelection();
        if (index >= 0) overlayFocus(true);
        recycle(items);
        root.recycle();
    }

    @Override protected boolean onKeyEvent(KeyEvent event) {
        int key = event.getKeyCode();
        if (event.getAction() == KeyEvent.ACTION_UP && held.get(key)) {
            held.delete(key);
            return true;
        }
        boolean direction = key >= Direction.UP && key <= Direction.RIGHT;
        boolean confirm = key == KeyEvent.KEYCODE_DPAD_CENTER
                || key == KeyEvent.KEYCODE_BUTTON_A
                || (key == KeyEvent.KEYCODE_ENTER
                    && (event.getScanCode() == 304 || event.getDeviceId() == -1));
        if ((!direction && !confirm) || event.getAction() != KeyEvent.ACTION_DOWN) return false;
        navigationCallbacks++;
        AccessibilityNodeInfo root = applicationRoot();
        mode = scope(root);
        lastKeyScope = mode;
        if (!"locales".equals(mode) && !"files".equals(mode)) {
            if (root != null) root.recycle();
            return false;
        }
        held.put(key, true);
        keyDownCount++;
        List<AccessibilityNodeInfo> items = new ArrayList<>();
        collectItems(root, items);
        int index = current(items);
        if (index < 0) {
            index = initial(items);
            if (index >= 0) select(items.get(index));
        } else if (direction) {
            int[][] boxes = new int[items.size()][4];
            for (int i = 0; i < items.size(); i++) {
                Rect b = new Rect();
                items.get(i).getBoundsInScreen(b);
                boxes[i] = new int[] {b.left, b.top, b.right, b.bottom};
            }
            int next = Direction.next(boxes, index, key);
            if (next >= 0) select(items.get(next));
            else scrollSelection(key);
        } else if (event.getRepeatCount() == 0 && index >= 0) {
            AccessibilityNodeInfo target = items.get(index);
            releaseForAction();
            if ("locales".equals(mode) && localeRow(target)) {
                lastAction = false;
                for (AccessibilityNodeInfo.AccessibilityAction action : target.getActionList()) {
                    if (moveTop != 0 && action.getId() == moveTop) {
                        lastAction = target.performAction(moveTop);
                        break;
                    }
                }
            } else {
                lastAction = target.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            }
            actionCount++;
            handler.postDelayed(refreshTask, 250);
        }
        recycle(items);
        root.recycle();
        return true;
    }

    private boolean scrollSelection(int key) {
        AccessibilityNodeInfo node = selected == null ? null : selected.getParent();
        while (node != null) {
            boolean horizontal = String.valueOf(node.getClassName()).contains("Horizontal");
            boolean matches = horizontal == (key == Direction.LEFT || key == Direction.RIGHT);
            int action = key == Direction.UP || key == Direction.LEFT
                    ? AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
                    : AccessibilityNodeInfo.ACTION_SCROLL_FORWARD;
            if (matches && node.isScrollable() && node.isVisibleToUser()
                    && node.performAction(action)) {
                node.recycle();
                handler.postDelayed(refreshTask, 200);
                return true;
            }
            AccessibilityNodeInfo parent = node.getParent();
            node.recycle();
            node = parent;
        }
        return false;
    }

    private static void recycle(List<AccessibilityNodeInfo> items) {
        for (AccessibilityNodeInfo item : items) item.recycle();
    }

    @Override protected void dump(FileDescriptor fd, PrintWriter writer, String[] args) {
        writer.println("mode=" + mode + " moveTopId=" + moveTop
                + " keyDownCount=" + keyDownCount + " actionCount=" + actionCount
                + " lastAction=" + lastAction + " navigationCallbacks=" + navigationCallbacks
                + " lastKeyScope=" + lastKeyScope + " flags=" + getServiceInfo().flags);
        if (selected != null) {
            Rect bounds = new Rect();
            selected.getBoundsInScreen(bounds);
            writer.println("selectedBounds=" + bounds.toShortString()
                    + " selectedId=" + selected.getViewIdResourceName());
            for (AccessibilityNodeInfo.AccessibilityAction action : selected.getActionList()) {
                writer.println("actionId=" + action.getId());
            }
        }
    }

    private final class FocusRing extends View {
        private final Paint paint = new Paint();
        private Rect bounds;
        private int axisKey;
        private final Runnable repeat = new Runnable() {
            @Override public void run() {
                if (axisKey == 0) return;
                navigate(axisKey);
                handler.postDelayed(this, 160);
            }
        };

        FocusRing(Context context) {
            super(context);
            setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            setFocusableInTouchMode(true);
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(Color.argb(20, 0, 0, 0));
            paint.setAntiAlias(true);
        }

        void stopRepeat() {
            axisKey = 0;
            handler.removeCallbacks(repeat);
        }

        private void navigate(int key) {
            NavigationService.this.onKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, key));
            NavigationService.this.onKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, key));
        }

        @Override public boolean dispatchKeyEvent(KeyEvent event) {
            int code = event.getKeyCode();
            if (code == KeyEvent.KEYCODE_BUTTON_B || code == KeyEvent.KEYCODE_BACK
                    || code == KeyEvent.KEYCODE_ESCAPE) {
                if (event.getAction() == KeyEvent.ACTION_UP && !event.isCanceled()) back();
                return true;
            }
            if (NavigationService.this.onKeyEvent(event)) return true;
            return super.dispatchKeyEvent(event);
        }

        @Override public boolean onGenericMotionEvent(MotionEvent event) {
            if (event.isFromSource(InputDevice.SOURCE_JOYSTICK)
                    && event.getActionMasked() == MotionEvent.ACTION_MOVE) {
                float x = event.getAxisValue(MotionEvent.AXIS_HAT_X);
                float y = event.getAxisValue(MotionEvent.AXIS_HAT_Y);
                int key = x < -0.5f ? Direction.LEFT : x > 0.5f ? Direction.RIGHT
                        : y < -0.5f ? Direction.UP : y > 0.5f ? Direction.DOWN : 0;
                if (key != axisKey) {
                    stopRepeat();
                    axisKey = key;
                    if (key != 0) {
                        navigate(key);
                        handler.postDelayed(repeat, 400);
                    }
                }
                return true;
            }
            return super.onGenericMotionEvent(event);
        }

        void show(Rect rect) {
            bounds = rect == null ? null : new Rect(rect);
            invalidate();
        }

        @Override protected void onDraw(Canvas canvas) {
            if (bounds == null) return;
            int[] location = new int[2];
            getLocationOnScreen(location);
            Rect local = new Rect(bounds);
            local.offset(-location[0], -location[1]);
            canvas.drawRect(local, paint);
        }
    }
}
