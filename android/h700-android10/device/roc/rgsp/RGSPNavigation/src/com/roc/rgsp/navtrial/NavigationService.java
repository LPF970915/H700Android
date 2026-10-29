package com.roc.rgsp.navtrial;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.SparseBooleanArray;
import android.view.KeyEvent;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
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
    private static final String AT4K = "com.overdevs.at4k";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final SparseBooleanArray held = new SparseBooleanArray();
    private final Runnable refreshTask = () -> refresh();
    private AccessibilityNodeInfo selected;
    private String selectedIdentity;
    private String armedIdentity;
    private int armedKey;
    private final Runnable documentLongPress = () -> activateLongDocument();
    private int pendingScroll;
    private long pendingScrollUntil;
    private int pendingScrollWindow;
    private String pendingRangeKey;
    private String pendingRangeTitle;
    private long pendingRangeUntil;
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
    private MouseController mouse;
    private final MenuHotkey menu = new MenuHotkey();
    private int menuHomeCount, menuShadeCount;
    private boolean shadeBack;
    private int lastInputKey, lastInputScan, lastInputAction, shadeCloseCount;
    private final Runnable menuHold = () -> {
        if (menu.fireLong(SystemClock.uptimeMillis())) menuAction(MenuHotkey.QUICK_SETTINGS);
        scheduleMenu();
    };

    private void scheduleMenu() {
        handler.removeCallbacks(menuHold);
        long delay = menu.nextDelay(SystemClock.uptimeMillis());
        if (delay >= 0) handler.postDelayed(menuHold, delay);
    }

    private void menuAction(int action) {
        if (mouse != null) mouse.exit();
        releaseForAction(); clearSelection(); held.clear();
        if (action == MenuHotkey.HOME) {
            menuHomeCount++; performGlobalAction(GLOBAL_ACTION_HOME);
        } else {
            menuShadeCount++; performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS);
        }
        handler.postDelayed(refreshTask, 550);
    }

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
        if (android.provider.Settings.Global.getInt(getContentResolver(), "rgsp_mouse_enabled", 1)==1) {
        mouse = new MouseController(this, handler, windows, new MouseController.Surface() {
            @Override public void show(float x, float y, boolean pressed) {
                ring.showCursor(x, y, pressed);
            }

            @Override public void capture(boolean capture) {
                // HAT motion requires window focus on this Android 10 BSP.
                // ALT_FOCUSABLE_IM leaves the real editor/IME relationship intact.
                overlayParams.flags |= WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM;
                overlayFocus(capture);
                windows.updateViewLayout(ring, overlayParams);
            }

            @Override public void ended() {
                overlayParams.flags &= ~WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM;
                overlayFocus(false);
                windows.updateViewLayout(ring, overlayParams);
                handler.postDelayed(refreshTask, 100);
            }
        });
        }
        refresh();
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        if(event.getEventType()==AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED && ring!=null) ring.stopRepeat();
        handler.removeCallbacks(refreshTask);
        handler.postDelayed(refreshTask, 100);
    }

    @Override public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        if(ring!=null) ring.stopRepeat();
        held.clear(); armedIdentity=null; armedKey=0;
        handler.removeCallbacks(refreshTask);handler.postDelayed(refreshTask,250);
    }

    @Override public void onInterrupt() {
        menu.clear(); handler.removeCallbacks(menuHold);
        if (mouse != null) mouse.exit();
        clearSelection();
    }

    @Override public void onDestroy() {
        if (mouse != null) mouse.destroy();
        handler.removeCallbacksAndMessages(null);
        clearSelection();
        if (windows != null && ring != null) windows.removeView(ring);
        super.onDestroy();
    }

    private boolean editorActive(AccessibilityNodeInfo root) {
        // Editors participate in traversal when the IME is hidden. Once shown,
        // the real IME must retain the controller and its normal editor behavior.
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
        if ("com.android.systemui".equals(pkg)) return shadeRoot(root) ? "shade" : "inactive";
        if (AT4K.equals(pkg)) {
            if (editorActive(root)) return "editor";
            // Keep native HOME navigation. Only the launcher's narrow settings
            // panel needs our action/scroll traversal on this small display.
            return at4kPanel(root) && !at4kNativeModal(root) ? "settings" : "inactive";
        }
        if (!SETTINGS.equals(pkg) && !FILES.equals(pkg)
                && !"com.android.settings.intelligence".equals(pkg)
                && !"com.android.permissioncontroller".equals(pkg)
                && !"com.android.inputmethod.latin".equals(pkg)
                && !"com.android.providers.media".equals(pkg)) return "inactive";
        if (editorActive(root)) return "editor";
        if (FILES.equals(pkg)) return "files";
        List<AccessibilityNodeInfo> lists = root.findAccessibilityNodeInfosByViewId(
                SETTINGS + ":id/dragList");
        boolean found = false;
        for (AccessibilityNodeInfo list : lists) {
            found |= list.isVisibleToUser();
            list.recycle();
        }
        return found ? "locales" : "settings";
    }

    private boolean at4kPanel(AccessibilityNodeInfo node) {
        if (node.isVisibleToUser() && node.isScrollable()) {
            Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
            android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
            windows.getDefaultDisplay().getRealMetrics(metrics);
            if (bounds.width() > metrics.widthPixels / 4
                    && bounds.width() < metrics.widthPixels * 9 / 10
                    && bounds.height() > metrics.heightPixels / 2) return true;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child == null) continue;
            boolean found = at4kPanel(child);
            child.recycle();
            if (found) return true;
        }
        return false;
    }

    private boolean at4kOutsidePanel(AccessibilityNodeInfo node) {
        Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
        android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
        windows.getDefaultDisplay().getRealMetrics(metrics);
        if (node.isVisibleToUser() && !bounds.isEmpty()
                && bounds.left > 0 && bounds.left < metrics.widthPixels / 4
                && (node.isClickable() || node.getText() != null)) return true;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child == null) continue;
            boolean found = at4kOutsidePanel(child); child.recycle();
            if (found) return true;
        }
        return false;
    }

    private boolean at4kNativeModal(AccessibilityNodeInfo node) {
        // AT4K's custom full-width dialogs flatten their semantics beside the
        // still-exposed narrow menu. Their original grid key handlers must own
        // focus; otherwise a helper can activate the covered menu underneath.
        Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
        android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
        windows.getDefaultDisplay().getRealMetrics(metrics);
        // Color palettes use a full-width clickable dismissal backdrop rather
        // than the sibling layout used by App Manager. Keep their native grid.
        if (node.isVisibleToUser() && node.isClickable()
                && bounds.width() > metrics.widthPixels * 95 / 100
                && bounds.height() > metrics.heightPixels / 2) return true;
        boolean panelBefore = false;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child == null) continue;
            boolean modal = (panelBefore && at4kOutsidePanel(child)) || at4kNativeModal(child);
            panelBefore |= at4kPanel(child);
            child.recycle();
            if (modal) return true;
        }
        return false;
    }

    private boolean managed() {
        return "locales".equals(mode) || "files".equals(mode) || "settings".equals(mode)
                || "shade".equals(mode);
    }

    private boolean shadeRoot(AccessibilityNodeInfo root) {
        if (!"com.android.systemui".equals(String.valueOf(root.getPackageName()))) return false;
        List<AccessibilityNodeInfo> panels = root.findAccessibilityNodeInfosByViewId(
                "com.android.systemui:id/quick_settings_panel");
        boolean visible = false;
        for (AccessibilityNodeInfo panel : panels) {
            Rect bounds = new Rect(); panel.getBoundsInScreen(bounds);
            visible |= panel.isVisibleToUser() && bounds.height() > 100;
            panel.recycle();
        }
        return visible;
    }

    private AccessibilityNodeInfo applicationRoot() {
        if (!((PowerManager) getSystemService(POWER_SERVICE)).isInteractive()
                || ((KeyguardManager) getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked()) {
            return null;
        }
        AccessibilityNodeInfo result = null;
        AccessibilityNodeInfo shade = null;
        boolean systemFocused = false;
        for (AccessibilityWindowInfo window : getWindows()) {
            if (window.isFocused() && window.getType() == AccessibilityWindowInfo.TYPE_SYSTEM) {
                systemFocused = true;
            }
            if (window.getType() == AccessibilityWindowInfo.TYPE_SYSTEM) {
                AccessibilityNodeInfo root = window.getRoot();
                if (root != null) {
                    if (shadeRoot(root)) {
                        if (shade != null) shade.recycle();
                        shade = AccessibilityNodeInfo.obtain(root);
                    }
                    root.recycle();
                }
            }
            if (window.getType() == AccessibilityWindowInfo.TYPE_APPLICATION
                    && (result == null || window.isFocused())) {
                if (result != null) result.recycle();
                result = window.getRoot();
            }
            window.recycle();
        }
        if (shade != null) { if (result != null) result.recycle(); return shade; }
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
        AccessibilityNodeInfo root = applicationRoot();
        if (root != null && "shade".equals(scope(root))) {
            root.recycle(); collapseShade(); return;
        }
        // Inspect the IME before changing focus: an editor may request it again
        // when our overlay gives the dialog its window focus back.
        boolean canCancel = root != null && "settings".equals(scope(root));
        releaseForAction();
        clearSelection();
        if (canCancel && "com.android.settings.intelligence".equals(
                String.valueOf(root.getPackageName())) && navigateSearchUp(root)) {
            root.recycle();
            handler.postDelayed(refreshTask, 550);
            return;
        }
        boolean cancelled = false;
        if (canCancel) {
            // Some edit dialogs ignore injected global BACK on this BSP. Use
            // their explicit negative Cancel action after the IME is hidden.
            // Never choose an affirmative/neutral action or cancel through IME.
            List<AccessibilityNodeInfo> buttons = root.findAccessibilityNodeInfosByViewId(
                    "android:id/button2");
            for (AccessibilityNodeInfo button : buttons) {
                if (!cancelled && button.isVisibleToUser() && button.isEnabled()
                        && button.isClickable() && android.text.TextUtils.equals(
                        button.getText(), getString(android.R.string.cancel))) {
                    lastAction = button.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                    actionCount++;
                    // A false return may still dismiss asynchronously. Never
                    // follow this with another BACK into the parent page.
                    cancelled = true;
                }
                button.recycle();
            }
        }
        if (root != null) root.recycle();
        if (cancelled) {
            handler.postDelayed(refreshTask, 550);
            return;
        }
        handler.postDelayed(() -> performGlobalAction(GLOBAL_ACTION_BACK), 80);
        handler.postDelayed(refreshTask, 550);
    }

    private void collapseShade() {
        shadeCloseCount++;
        releaseForAction(); clearSelection(); held.clear();
        try {
            Object bar = getSystemService("statusbar");
            Class.forName("android.app.StatusBarManager").getMethod("collapsePanels").invoke(bar);
        } catch (Exception error) {
            android.util.Log.w("RGSPNavigation", "Shade collapse failed", error);
            performGlobalAction(GLOBAL_ACTION_BACK);
        }
        handler.postDelayed(refreshTask, 550);
    }

    private boolean navigateSearchUp(AccessibilityNodeInfo root) {
        // SearchAutoComplete can consume BACK to clear focus, then regain it
        // when this controller overlay refreshes. Use SearchActivity's native
        // toolbar Up action (onNavigateUp finishes the activity) after IME hide.
        List<AccessibilityNodeInfo> toolbars = root.findAccessibilityNodeInfosByViewId(
                "com.android.settings.intelligence:id/search_toolbar");
        AccessibilityNodeInfo up = null;
        int matches = 0;
        for (AccessibilityNodeInfo toolbar : toolbars) {
            for (int i = 0; i < toolbar.getChildCount(); i++) {
                AccessibilityNodeInfo child = toolbar.getChild(i);
                if (child == null) continue;
                if (child.isVisibleToUser() && child.isEnabled() && child.isClickable()
                        && "android.widget.ImageButton".contentEquals(child.getClassName())
                        && !android.text.TextUtils.isEmpty(child.getContentDescription())) {
                    matches++;
                    if (up != null) up.recycle();
                    up = AccessibilityNodeInfo.obtain(child);
                }
                child.recycle();
            }
            toolbar.recycle();
        }
        if (matches != 1 || up == null) {
            if (up != null) up.recycle();
            return false;
        }
        lastAction = up.performAction(AccessibilityNodeInfo.ACTION_CLICK);
        actionCount++;
        up.recycle();
        // An action may finish asynchronously even if its return is false.
        return true;
    }

    private boolean localeRow(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo parent = node.getParent();
        boolean result = parent != null
                && (SETTINGS + ":id/dragList").equals(parent.getViewIdResourceName());
        if (parent != null) parent.recycle();
        return result;
    }

    private boolean visibleCheckableDescendant(AccessibilityNodeInfo node) {
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                boolean found = child.isVisibleToUser()
                        && (child.isCheckable() || visibleCheckableDescendant(child));
                child.recycle();
                if (found) return true;
            }
        }
        return false;
    }

    private Rect focusBounds(AccessibilityNodeInfo node) {
        Rect bounds = new Rect(); node.getBoundsInScreen(bounds);
        if ("settings".equals(mode)) {
            AccessibilityNodeInfo ancestor = node.getParent();
            while (ancestor != null) {
                String kind = String.valueOf(ancestor.getClassName());
                if (kind.contains("ViewPager") || kind.contains("RecyclerView")
                        || kind.endsWith("ScrollView") || kind.endsWith("ListView")
                        || kind.endsWith("GridView")) {
                    Rect viewport = new Rect(); ancestor.getBoundsInScreen(viewport);
                    if (!bounds.intersect(viewport)) bounds.setEmpty();
                }
                AccessibilityNodeInfo next = ancestor.getParent();
                ancestor.recycle(); ancestor = next;
            }
            return bounds;
        }
        if (!"files".equals(mode)) return bounds;
        AccessibilityNodeInfo parent = AccessibilityNodeInfo.obtain(node);
        Rect viewport = null;
        while (parent != null) {
            boolean list = (FILES + ":id/dir_list").equals(parent.getViewIdResourceName());
            if (list) { viewport = new Rect(); parent.getBoundsInScreen(viewport); }
            AccessibilityNodeInfo next = list ? null : parent.getParent();
            parent.recycle(); parent = next;
        }
        if (viewport == null) return bounds;
        AccessibilityWindowInfo window = node.getWindow();
        AccessibilityNodeInfo root = window == null ? null : window.getRoot();
        if (window != null) window.recycle();
        if (root != null) {
            // RecyclerView's padded/covered rows can remain in the AX tree.
            // Only the actual directory viewport is a navigation/paint target.
            for (String id : new String[] {FILES + ":id/app_bar", FILES + ":id/container_save"}) {
                List<AccessibilityNodeInfo> covers = root.findAccessibilityNodeInfosByViewId(id);
                for (AccessibilityNodeInfo cover : covers) {
                    Rect area = new Rect(); cover.getBoundsInScreen(area);
                    if (cover.isVisibleToUser() && !area.isEmpty()
                            && area.left < viewport.right && viewport.left < area.right) {
                        if (id.endsWith("/app_bar")) viewport.top = Math.max(viewport.top, area.bottom);
                        else viewport.bottom = Math.min(viewport.bottom, area.top);
                    }
                    cover.recycle();
                }
            }
            root.recycle();
        }
        if (!bounds.intersect(viewport)) bounds.setEmpty();
        return bounds;
    }

    private void collect(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> items) {
        if ("settings".equals(mode)) { collectSettings(node, items); return; }
        if (!node.refresh()) return;
        if (!node.isVisibleToUser() || !node.isEnabled()) return;
        // Bottom-sheet pointer dismiss scrims cover all real choices. They are
        // not keyboard controls; B already supplies the explicit cancel path.
        String resource = node.getViewIdResourceName();
        if ("shade".equals(mode) && node.getRangeInfo() != null) {
            Rect bounds = focusBounds(node);
            if (!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
            return;
        }
        if ("files".equals(mode) && resource != null && resource.endsWith("/touch_outside")) return;
        if (node.isEditable()) {
            Rect bounds = focusBounds(node);
            if (!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
            return;
        }
        // Read-only detail pages still need an explicit D-pad scroll target.
        // Lists keep their individual item targets and embedded buttons keep
        // their own actions; this fallback owns only plain text scroll panes.
        if ("files".equals(mode) && String.valueOf(node.getClassName()).endsWith("ScrollView")
                && node.isScrollable() && !actionableDescendant(node)) {
            Rect bounds = focusBounds(node);
            if (!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
            return;
        }
        boolean row = "locales".equals(mode) && localeRow(node);
        if (row && visibleCheckableDescendant(node)) {
            // Remove mode replaces drag actions with real checkbox controls.
            // Selecting the outer row would still try the normal reorder action.
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) { collect(child, items); child.recycle(); }
            }
            return;
        }
        boolean doc = (FILES + ":id/item_root").equals(node.getViewIdResourceName());
        if (row || doc || node.isClickable()) {
            Rect bounds = focusBounds(node);
            if (!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
            // Locale rows own their drag action. Document rows may also
            // contain a genuine Preview button, just as storage roots have
            // Eject. Retain each independent child action in traversal.
            if (row) return;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                collect(child, items);
                child.recycle();
            }
        }
    }

    private String title(AccessibilityNodeInfo node) {
        String liveName = liveStatsRowName(node);
        if (!liveName.isEmpty()) return liveName;
        List<String> labels = new ArrayList<>();
        collectLabels(node, labels);
        return android.text.TextUtils.join(" | ", labels);
    }

    private String liveStatsRowName(AccessibilityNodeInfo node) {
        // Running-process rows update size/description/uptime independently of
        // user focus. Those values must not invalidate a held confirm key or
        // make a selected row fall back to the list's first item.
        if (!"settings".equals(mode)
                || !"android.widget.GridLayout".equals(String.valueOf(node.getClassName()))
                || node.getCollectionItemInfo() == null) return "";
        List<AccessibilityNodeInfo> names = node.findAccessibilityNodeInfosByViewId(
                "com.android.settings:id/name");
        List<AccessibilityNodeInfo> sizes = node.findAccessibilityNodeInfosByViewId(
                "com.android.settings:id/size");
        List<AccessibilityNodeInfo> descriptions = node.findAccessibilityNodeInfosByViewId(
                "com.android.settings:id/description");
        List<AccessibilityNodeInfo> uptimes = node.findAccessibilityNodeInfosByViewId(
                "com.android.settings:id/uptime");
        String name = "";
        if (names.size() == 1 && sizes.size() == 1 && descriptions.size() == 1
                && uptimes.size() == 1 && names.get(0).getText() != null) {
            name = names.get(0).getText().toString();
        }
        recycle(names); recycle(sizes); recycle(descriptions); recycle(uptimes);
        return name;
    }

    private void collectLabels(AccessibilityNodeInfo node, List<String> labels) {
        if (labels.size() >= 3) return;
        String id = node.getViewIdResourceName();
        String kind = String.valueOf(node.getClassName());
        if ((id != null && id.endsWith("/summary")) || node.isEditable()
                || node.isPassword() || node.getRangeInfo() != null
                || kind.endsWith("Switch") || kind.endsWith("ToggleButton")) return;
        CharSequence own = node.getText();
        if (own == null || own.length() == 0) own = node.getContentDescription();
        if (own != null && own.length() > 0) {
            if (!labels.contains(own.toString())) labels.add(own.toString());
            return;
        }
        for (int i=0; i<node.getChildCount(); i++) {
            AccessibilityNodeInfo child=node.getChild(i);
            if (child != null) {
                collectLabels(child, labels); child.recycle();
                if (labels.size() >= 3) return;
            }
        }
    }

    private String identity(AccessibilityNodeInfo node) {
        boolean range = node.getRangeInfo() != null;
        String semantic=titleCount(node)==1 ? preferenceTitle(node) : title(node);
        if(hasChangingValue(node)) {
            // A range's adjacent value label changes after each adjustment.
            // Only an explicit owning preference title can identify that range.
            if (range && titleCount(node) != 1) semantic = "";
            AccessibilityNodeInfo parent=node.getParent();
            while(parent!=null && semantic.isEmpty()) {
                semantic=titleCount(parent)==1 ? preferenceTitle(parent)
                        : range ? "" : title(parent);
                AccessibilityNodeInfo next=parent.getParent();parent.recycle();parent=next;
            }
            if(parent!=null) parent.recycle();
        }
        AccessibilityNodeInfo parent=node.getParent();
        String parentId=parent==null ? "" : String.valueOf(parent.getViewIdResourceName());
        if(parent!=null) parent.recycle();
        return node.getWindowId()+"|"+node.getViewIdResourceName()+"|"
                +node.getClassName()+"|"+parentId+"|"+semantic+collectionPosition(node);
    }

    private String collectionPosition(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo cursor = AccessibilityNodeInfo.obtain(node);
        while (cursor != null) {
            AccessibilityNodeInfo.CollectionItemInfo item = cursor.getCollectionItemInfo();
            if (item != null) {
                String position = "|#collection=" + item.getRowIndex() + "," + item.getColumnIndex();
                cursor.recycle();
                return position;
            }
            AccessibilityNodeInfo parent = cursor.getParent();
            cursor.recycle();
            cursor = parent;
        }
        return "|#collection=";
    }

    private boolean hasChangingValue(AccessibilityNodeInfo node) {
        String kind=String.valueOf(node.getClassName());
        if(node.isEditable() || node.getRangeInfo()!=null || kind.endsWith("Switch")
                || kind.endsWith("CheckBox") || kind.endsWith("ToggleButton")) return true;
        for(int i=0;i<node.getChildCount();i++) {
            AccessibilityNodeInfo child=node.getChild(i);
            if(child!=null) {boolean found=hasChangingValue(child);child.recycle();if(found)return true;}
        }
        return false;
    }

    private String preferenceTitle(AccessibilityNodeInfo node) {
        String id=node.getViewIdResourceName();
        if(id!=null && id.endsWith("/title") && node.getText()!=null) return node.getText().toString();
        for(int i=0;i<node.getChildCount();i++) {
            AccessibilityNodeInfo child=node.getChild(i);
            if(child!=null) {String text=preferenceTitle(child);child.recycle();if(!text.isEmpty())return text;}
        }
        return "";
    }

    private int titleCount(AccessibilityNodeInfo node) {
        int count=0;
        String id=node.getViewIdResourceName();
        if (id != null && id.endsWith("/title") && node.getText()!=null) count++;
        for (int i=0;i<node.getChildCount();i++) {
            AccessibilityNodeInfo child=node.getChild(i);
            if(child!=null) {count+=titleCount(child);child.recycle();}
        }
        return count;
    }

    private boolean adjustableRange(AccessibilityNodeInfo node) {
        if (node.getRangeInfo() == null) return false;
        // RangeInfo also describes decorative storage usage bars. Keep disabled
        // sliders readable, but only sliders or advertised adjustment targets
        // belong in the controller navigation order.
        if (String.valueOf(node.getClassName()).endsWith("SeekBar")) return true;
        for (AccessibilityNodeInfo.AccessibilityAction action : node.getActionList()) {
            int id = action.getId();
            if (id == AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.getId()
                    || id == AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
                    || id == AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD) return true;
        }
        return false;
    }

    private boolean actionableDescendant(AccessibilityNodeInfo node) {
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child == null) continue;
            boolean found = child.isVisibleToUser() && (child.isClickable()
                    || child.isEditable() || adjustableRange(child)
                    || ("settings".equals(mode)
                        && supportsAction(child, AccessibilityNodeInfo.ACTION_CLICK))
                    || String.valueOf(child.getClassName()).endsWith("Button")
                    || actionableDescendant(child));
            child.recycle();
            if (found) return true;
        }
        return false;
    }

    private boolean canConfirm(AccessibilityNodeInfo node) {
        return node.isEnabled() && (node.isClickable() || node.isEditable()
                || ("settings".equals(mode)
                    && supportsAction(node, AccessibilityNodeInfo.ACTION_CLICK))
                || ("files".equals(mode) && documentRow(node)
                    && supportsAction(node, AccessibilityNodeInfo.ACTION_CLICK)));
    }

    private boolean documentRow(AccessibilityNodeInfo node) {
        return FILES.equals(String.valueOf(node.getPackageName()))
                && (FILES + ":id/item_root").equals(node.getViewIdResourceName());
    }

    private boolean supportsAction(AccessibilityNodeInfo node, int id) {
        for (AccessibilityNodeInfo.AccessibilityAction action : node.getActionList()) {
            if (action.getId() == id) return true;
        }
        return false;
    }

    private void collectSettings(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> items) {
        if(!node.refresh()) return;
        if (!node.isVisibleToUser()) return;
        String kind=String.valueOf(node.getClassName());
        // Certificate/other read-only dialogs expose a scrollable text pane,
        // not clickable text rows. Keep it as a direction-only target so the
        // body can scroll before focus exits to the dialog's action buttons.
        if (kind.endsWith("ScrollView") && node.isScrollable()
                && !actionableDescendant(node)) {
            Rect bounds=focusBounds(node);
            if (!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
            return;
        }
        boolean container=kind.contains("RecyclerView") || kind.endsWith("ListView")
                || kind.endsWith("GridView") || kind.endsWith("ScrollView")
                || kind.contains("ViewPager");
        boolean leaf=node.isEditable() || adjustableRange(node) || kind.endsWith("Button")
                || (node.isCheckable() && node.isClickable());
        boolean informationRow = node.getCollectionItemInfo() != null
                && titleCount(node) == 1 && !title(node).isEmpty()
                && !actionableDescendant(node);
        // Framework virtual cells (for example calendar dates) advertise CLICK
        // without setting isClickable/isFocusable. Respect their actual action.
        boolean actionOnlyClick = !container && !title(node).isEmpty()
                && supportsAction(node, AccessibilityNodeInfo.ACTION_CLICK);
        boolean actionable=leaf || actionOnlyClick || (node.isClickable() && !container
                && titleCount(node)<=1 && !title(node).isEmpty()) || informationRow;
        if (actionable) {
            Rect bounds=focusBounds(node);
            if(!bounds.isEmpty()) items.add(AccessibilityNodeInfo.obtain(node));
        }
        if (leaf) return;
        // Keep secondary switches/buttons as separate targets beside a row's action.
        for(int i=0;i<node.getChildCount();i++) {
            AccessibilityNodeInfo child=node.getChild(i);
            if(child!=null) {collectSettings(child,items);child.recycle();}
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
        removeCoveredByActionMode(root, items);
    }

    private boolean within(AccessibilityNodeInfo node, AccessibilityNodeInfo ancestor) {
        AccessibilityNodeInfo current = AccessibilityNodeInfo.obtain(node);
        while (current != null) {
            boolean same = current.equals(ancestor);
            AccessibilityNodeInfo parent = same ? null : current.getParent();
            current.recycle();
            if (same) return true;
            current = parent;
        }
        return false;
    }

    private void removeCoveredByActionMode(AccessibilityNodeInfo root,
            List<AccessibilityNodeInfo> items) {
        // AppCompat can keep the original toolbar exposed to accessibility
        // underneath its selection toolbar. Its covered icons are not targets.
        String[] ids = {String.valueOf(root.getPackageName()) + ":id/action_mode_bar",
                "android:id/action_context_bar"};
        for (String id : ids) {
            List<AccessibilityNodeInfo> bars = root.findAccessibilityNodeInfosByViewId(id);
            for (AccessibilityNodeInfo bar : bars) {
                Rect cover = new Rect(); bar.getBoundsInScreen(cover);
                if (bar.refresh() && bar.isVisibleToUser() && bar.getChildCount() > 0 && !cover.isEmpty()) {
                    for (int i = items.size() - 1; i >= 0; i--) {
                        AccessibilityNodeInfo item = items.get(i);
                        Rect bounds = new Rect(); item.getBoundsInScreen(bounds);
                        if (cover.contains(bounds.centerX(), bounds.centerY()) && !within(item, bar)) {
                            items.remove(i).recycle();
                        }
                    }
                }
                bar.recycle();
            }
        }
    }

    private void clearSelection() {
        handler.removeCallbacks(documentLongPress);
        if (selected != null) selected.recycle();
        selected = null;
        selectedIdentity = null;
        armedIdentity = null;
        armedKey = 0;
        pendingScroll = 0;
        if (ring != null) ring.show(null);
        overlayFocus(false);
    }

    private void select(AccessibilityNodeInfo node) {
        boolean changed = selected == null || !selected.equals(node);
        if (selected != null) selected.recycle();
        selected = AccessibilityNodeInfo.obtain(node);
        selectedIdentity = identity(node);
        if (changed) {
            if (!"settings".equals(mode)
                    || supportsAction(node, AccessibilityNodeInfo.ACTION_FOCUS)) {
                node.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            }
            if (("files".equals(mode)
                    || ("settings".equals(mode) && insideSettingsList(node)))
                    && !node.isEditable()
                    && supportsAction(node, AccessibilityNodeInfo.AccessibilityAction.ACTION_SHOW_ON_SCREEN.getId())) {
                node.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_SHOW_ON_SCREEN.getId());
            }
        }
        Rect bounds = focusBounds(node);
        // AT4K buttons already draw their native selected state.
        if (ring != null) ring.show(AT4K.equals(String.valueOf(node.getPackageName())) ? null : bounds);
    }

    private int current(List<AccessibilityNodeInfo> items) {
        if(pendingRangeKey!=null && SystemClock.uptimeMillis()<pendingRangeUntil) {
            for(int i=0;i<items.size();i++) {
                AccessibilityNodeInfo item=items.get(i);
                if(item.getRangeInfo()!=null && pendingRangeKey.equals(withoutWindow(identity(item)))
                        && pendingRangeTitle.equals(windowTitle(item))) return i;
            }
        }
        if (selected != null) {
            String[] keys = new String[items.size()];
            boolean[] sameNode = new boolean[items.size()];
            for (int i = 0; i < items.size(); i++) {
                keys[i] = identity(items.get(i));
                sameNode[i] = selected.equals(items.get(i));
            }
            return FocusIdentity.find(keys, sameNode, selectedIdentity);
        }
        return -1;
    }

    private String withoutWindow(String key) { return key.substring(key.indexOf('|')+1); }

    private String windowTitle(AccessibilityNodeInfo node) {
        AccessibilityWindowInfo window=node.getWindow();
        if(window==null) return "";
        String title=String.valueOf(window.getTitle());window.recycle();return title;
    }

    private int initial(List<AccessibilityNodeInfo> items) {
        if ("shade".equals(mode)) {
            for (int i = 0; i < items.size(); i++) {
                AccessibilityNodeInfo parent = items.get(i).getParent();
                while (parent != null) {
                    boolean tile = "com.android.systemui:id/tile_page".equals(parent.getViewIdResourceName());
                    AccessibilityNodeInfo next = tile ? null : parent.getParent();
                    parent.recycle(); parent = next;
                    if (tile) return i;
                }
            }
        }
        if ("locales".equals(mode)) {
            for (int i = 0; i < items.size(); i++) {
                if (localeRow(items.get(i))) return i;
            }
        }
        if ("settings".equals(mode)) {
            for(int i=0;i<items.size();i++) if(items.get(i).isFocused()) return i;
            for(int i=0;i<items.size();i++) if(titleCount(items.get(i))==1) return i;
        }
        return items.isEmpty() ? -1 : 0;
    }

    // Request full visibility for real collection rows. Virtual calendar dates
    // live in a pager and retain their explicit previous/next-month controls.
    private boolean insideSettingsList(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo parent = node.getParent();
        while (parent != null) {
            String kind = String.valueOf(parent.getClassName());
            boolean pager = kind.contains("ViewPager");
            boolean list = kind.contains("ListView") || kind.contains("RecyclerView");
            AccessibilityNodeInfo next = parent.getParent();
            parent.recycle();
            parent = next;
            if (pager || list) {
                if (parent != null) parent.recycle();
                return !pager;
            }
        }
        return false;
    }

    private boolean insideScroller(AccessibilityNodeInfo node) {
        if (node.isScrollable() && node.getRangeInfo()==null) return true;
        AccessibilityNodeInfo parent=node.getParent();
        while(parent!=null) {
            boolean scroll=parent.isScrollable() && parent.getRangeInfo()==null;
            AccessibilityNodeInfo next=parent.getParent();parent.recycle();parent=next;
            if(scroll) {if(parent!=null)parent.recycle();return true;}
        }
        return false;
    }

    private int afterScroll(List<AccessibilityNodeInfo> items) {
        int result=-1;
        boolean reverse=pendingScroll==Direction.UP || pendingScroll==Direction.LEFT;
        for(int i=0;i<items.size();i++) if(insideScroller(items.get(i))) {
            result=i;
            if(!reverse) break;
        }
        return result;
    }

    private boolean awaitingScroll(AccessibilityNodeInfo root) {
        if (pendingScroll == 0) return false;
        if (SystemClock.uptimeMillis() >= pendingScrollUntil
                || root.getWindowId() != pendingScrollWindow) {
            pendingScroll = 0;
            return false;
        }
        return true;
    }

    private void refresh() {
        if (mouse != null && mouse.isActive()) {
            if (selected != null) selected.recycle();
            selected = null;
            ring.show(null);
            mode = "mouse";
            return;
        }
        if (SystemClock.uptimeMillis() < releaseUntil) {
            handler.removeCallbacks(refreshTask);
            handler.postDelayed(refreshTask, releaseUntil - SystemClock.uptimeMillis() + 20);
            return;
        }
        AccessibilityNodeInfo root = applicationRoot();
        mode = scope(root);
        if (!managed()) {
            clearSelection();
            if (root != null) root.recycle();
            return;
        }
        List<AccessibilityNodeInfo> items = new ArrayList<>();
        collectItems(root, items);
        int index = current(items);
        if (index < 0 && awaitingScroll(root)) {
            // Scroll actions expose the next page; start at its entering edge.
            index=afterScroll(items);
            if (index < 0) {
                recycle(items); root.recycle();
                handler.postDelayed(refreshTask, 100);
                return;
            }
            pendingScroll=0;
        }
        // An early refresh can still contain the old selected row. Keep the
        // pending direction until the actual layout removes it or it expires.
        awaitingScroll(root);
        if (index < 0) index = initial(items);
        if (index >= 0) select(items.get(index)); else clearSelection();
        if (index >= 0) overlayFocus(true);
        recycle(items);
        root.recycle();
    }

    @Override protected boolean onKeyEvent(KeyEvent event) {
        lastInputKey = event.getKeyCode(); lastInputScan = event.getScanCode();
        lastInputAction = event.getAction();
        int menuResult = menu.update(event.getDeviceId(), event.getKeyCode(), event.getScanCode(),
                (event.getFlags() & KeyEvent.FLAG_FALLBACK) != 0,
                event.getAction() == KeyEvent.ACTION_DOWN, event.isCanceled(), event.getEventTime());
        scheduleMenu();
        if (mouse != null && mouse.onKey(event)) return true;
        if (menuResult != MenuHotkey.PASS) {
            if (menuResult == MenuHotkey.HOME || menuResult == MenuHotkey.QUICK_SETTINGS)
                menuAction(menuResult);
            return true;
        }
        int key = event.getKeyCode();
        if (key == KeyEvent.KEYCODE_BUTTON_B || key == KeyEvent.KEYCODE_BACK
                || key == KeyEvent.KEYCODE_ESCAPE) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && !shadeBack) {
                AccessibilityNodeInfo root = applicationRoot();
                shadeBack = root != null && "shade".equals(scope(root));
                if (root != null) root.recycle();
            }
            if (shadeBack) {
                if (event.getAction() == KeyEvent.ACTION_UP) {
                    shadeBack = false;
                    if (!event.isCanceled()) collapseShade();
                }
                return true;
            }
        }
        if((key==KeyEvent.KEYCODE_MENU || key==KeyEvent.KEYCODE_BUTTON_SELECT)
                && event.getAction()==KeyEvent.ACTION_DOWN) {
            releaseForAction();return false;
        }
        if (event.getAction() == KeyEvent.ACTION_UP && held.get(key)) {
            held.delete(key);
            handler.removeCallbacks(documentLongPress);
            if (armedIdentity != null && key==armedKey) {
                String armed=armedIdentity; armedIdentity=null;
                armedKey=0;
                if (!event.isCanceled()) activate(armed);
            }
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
        if (!managed()) {
            if (root != null) root.recycle();
            return false;
        }
        held.put(key, true);
        keyDownCount++;
        List<AccessibilityNodeInfo> items = new ArrayList<>();
        collectItems(root, items);
        int index = current(items);
        if(index<0 && awaitingScroll(root)) {
            index=afterScroll(items);
            if (index < 0) {
                recycle(items); root.recycle();
                handler.postDelayed(refreshTask,100);
                return true;
            }
        }
        pendingScroll=0;
        if (index < 0) {
            index = initial(items);
            if (index >= 0) select(items.get(index));
        } else if (direction) {
            if (adjustRange(items.get(index),key)) {
                recycle(items); root.recycle(); return true;
            }
            pendingRangeKey=null;
            int[][] boxes = new int[items.size()][4];
            for (int i = 0; i < items.size(); i++) {
                Rect b = focusBounds(items.get(i));
                boxes[i] = new int[] {b.left, b.top, b.right, b.bottom};
            }
            // A full-width brightness slider is directly above every tile.
            // Its distant horizontal centre must not make Up skip to the clock.
            if ("shade".equals(mode) && (key == Direction.UP || key == Direction.DOWN)) {
                int x = (boxes[index][0] + boxes[index][2]) / 2;
                for (int i = 0; i < items.size(); i++) if (i != index
                        && items.get(i).getRangeInfo() != null
                        && boxes[i][0] < x && x < boxes[i][2]) {
                    boxes[i][0] = x - 1; boxes[i][2] = x + 1;
                }
            }
            int next = "shade".equals(mode) && (key == Direction.LEFT || key == Direction.RIGHT)
                    ? Direction.nextAligned(boxes, index, key) : Direction.next(boxes, index, key);
            boolean vertical = key == Direction.UP || key == Direction.DOWN;
            // Read-only rows cannot request native focus to reveal earlier
            // content. Scroll their container before escaping into a toolbar.
            boolean scrollBeforeExit = next >= 0 && vertical && insideScroller(items.get(index))
                    && !insideScroller(items.get(next)) && scrollSelection(key);
            if (scrollBeforeExit) { /* Preserve the pending scroll edge. */ }
            else if (next >= 0) select(items.get(next));
            else if(!scrollSelection(key) && items.get(index).getRangeInfo()!=null
                    && (key==Direction.UP || key==Direction.DOWN)) {
                // A vertical escape from a slider may reach a peer on the same
                // row, never an unrelated toolbar item diagonally above it.
                int side=Direction.nextAligned(boxes,index,key==Direction.DOWN ? Direction.RIGHT : Direction.LEFT);
                if(side>=0) select(items.get(side));
            }
        } else if (event.getRepeatCount() == 0 && index >= 0) {
            if (canConfirm(items.get(index))) {
                armedIdentity=identity(items.get(index));
                armedKey=key;
                if ("files".equals(mode) && documentRow(items.get(index))
                        && supportsAction(items.get(index), AccessibilityNodeInfo.ACTION_LONG_CLICK)) {
                    handler.removeCallbacks(documentLongPress);
                    handler.postDelayed(documentLongPress, ViewConfiguration.getLongPressTimeout());
                }
            } else {
                // Disabled entries remain readable and provide a path through
                // disabled-only pages, but confirmation must remain a no-op.
                armedIdentity=null; armedKey=0; lastAction=false;
            }
        }
        recycle(items);
        root.recycle();
        return true;
    }

    private void activate(String armed) {
        AccessibilityNodeInfo root=applicationRoot();
        mode=scope(root);
        if(root==null) return;
        if(!managed()) {root.recycle();return;}
        List<AccessibilityNodeInfo> items=new ArrayList<>(); collectItems(root,items);
        int index=current(items);
        if(index>=0 && canConfirm(items.get(index)) && armed.equals(identity(items.get(index)))) {
            AccessibilityNodeInfo target=items.get(index);
            pendingScroll=0;
            pendingRangeKey=null;
            releaseForAction();
            if ("locales".equals(mode) && localeRow(target)) {
                // Current Settings exposes a native click to promote this locale.
                // Retain the drag accessibility action for older Settings builds.
                lastAction = target.isClickable()
                        && target.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                for (AccessibilityNodeInfo.AccessibilityAction action : target.getActionList()) {
                    if (lastAction) break;
                    if (moveTop != 0 && action.getId() == moveTop) {
                        lastAction = target.performAction(moveTop);
                        break;
                    }
                }
            } else {
                if (target.isEditable()) {
                    // Releasing our focused overlay updates the IME client
                    // asynchronously. Clicking in this same callback can ask
                    // the IME to show while it still serves the overlay.
                    releaseUntil = SystemClock.uptimeMillis() + 1000;
                    target.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
                    handler.postDelayed(() -> activateEditor(armed), 200);
                } else {
                    lastAction = target.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                }
            }
            actionCount++;
            handler.postDelayed(refreshTask, 250);
        }
        recycle(items);
        root.recycle();
    }

    private void activateLongDocument() {
        String expected = armedIdentity;
        if (expected == null || !held.get(armedKey)) return;
        // A long confirm selects a document through DocumentsUI's own action.
        // Consume release even if the provider responds asynchronously.
        armedIdentity = null; armedKey = 0;
        AccessibilityNodeInfo root = applicationRoot();
        mode = scope(root);
        if (root == null) return;
        if ("files".equals(mode)) {
            List<AccessibilityNodeInfo> items = new ArrayList<>(); collectItems(root, items);
            int index = current(items);
            if (index >= 0 && items.get(index).isEnabled() && documentRow(items.get(index))
                    && expected.equals(identity(items.get(index)))
                    && supportsAction(items.get(index), AccessibilityNodeInfo.ACTION_LONG_CLICK)) {
                releaseForAction();
                lastAction = items.get(index).performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK);
                actionCount++;
                handler.postDelayed(refreshTask, 250);
            }
            recycle(items);
        }
        root.recycle();
    }

    private void activateEditor(String expectedIdentity) {
        AccessibilityNodeInfo root = applicationRoot();
        if (root == null) return;
        mode = scope(root);
        if (managed()) {
            AccessibilityNodeInfo input = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if (input != null) {
                if (input.isEditable() && input.isEnabled()
                        && expectedIdentity.equals(identity(input))) {
                    lastAction = input.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                }
                input.recycle();
            }
        }
        root.recycle();
        handler.postDelayed(refreshTask, 250);
    }

    private boolean adjustRange(AccessibilityNodeInfo target,int key) {
        target.refresh();
        AccessibilityNodeInfo.RangeInfo range=target.getRangeInfo();
        if(!"settings".equals(mode) || !target.isEnabled() || range==null
                || (key!=Direction.LEFT && key!=Direction.RIGHT)) return false;
        float step=range.getType()==AccessibilityNodeInfo.RangeInfo.RANGE_TYPE_INT ? 1 : (range.getMax()-range.getMin())/20f;
        float value=Math.max(range.getMin(),Math.min(range.getMax(),range.getCurrent()+(key==Direction.LEFT ? -step : step)));
        pendingRangeKey=withoutWindow(identity(target)); pendingRangeTitle=windowTitle(target);
        pendingRangeUntil=SystemClock.uptimeMillis()+5000;
        Bundle args=new Bundle(); args.putFloat(AccessibilityNodeInfo.ACTION_ARGUMENT_PROGRESS_VALUE,value);
        boolean precise=false;
        for(AccessibilityNodeInfo.AccessibilityAction action:target.getActionList()) {
            precise |= action.getId()==AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.getId();
        }
        // Exactly one advertised action per press: a failed return code must not
        // cause a second increment after a widget already changed its value.
        lastAction=precise ? target.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_PROGRESS.getId(),args)
                : target.performAction(key==Direction.LEFT ? AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD : AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
        actionCount++; handler.postDelayed(refreshTask,100); return true;
    }

    private boolean scrollSelection(int key) {
        AccessibilityNodeInfo node = selected == null ? null : AccessibilityNodeInfo.obtain(selected);
        while (node != null) {
            String kind = String.valueOf(node.getClassName());
            boolean pager = kind.contains("ViewPager");
            boolean horizontal = kind.contains("Horizontal") || pager;
            // A paged choice grid has explicit page controls. Traversing its
            // dates must not swipe months when focus reaches a row boundary.
            boolean pagedChoices = "settings".equals(mode) && pager
                    && actionableDescendant(node);
            boolean matches = !pagedChoices
                    && horizontal == (key == Direction.LEFT || key == Direction.RIGHT);
            int action = key == Direction.UP || key == Direction.LEFT
                    ? AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
                    : AccessibilityNodeInfo.ACTION_SCROLL_FORWARD;
            if (matches && node.isScrollable() && node.isVisibleToUser()
                    && node.performAction(action)) {
                node.recycle();
                pendingScroll=key;
                pendingScrollWindow=selected.getWindowId();
                pendingScrollUntil=SystemClock.uptimeMillis()+2500;
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
        AccessibilityServiceInfo serviceInfo = getServiceInfo();
        writer.println("menuHome=" + menuHomeCount + " menuShade=" + menuShadeCount);
        writer.println("lastInput=" + lastInputKey + "/" + lastInputScan + "/" + lastInputAction
                + " shadeClose=" + shadeCloseCount);
        writer.println("navigationVersion=36 mode=" + mode + " moveTopId=" + moveTop
                + " keyDownCount=" + keyDownCount + " actionCount=" + actionCount
                + " lastAction=" + lastAction + " navigationCallbacks=" + navigationCallbacks
                + " lastKeyScope=" + lastKeyScope + " flags=" + (serviceInfo == null ? 0 : serviceInfo.flags));
        if (mouse != null) mouse.dump(writer);
        if (selected != null) {
            Rect bounds = new Rect();
            selected.getBoundsInScreen(bounds);
            if (ring != null && ring.bounds != null) writer.println("visibleBounds=" + ring.bounds.toShortString());
            writer.println("selectedBounds=" + bounds.toShortString()
                    + " selectedId=" + selected.getViewIdResourceName());
            for (AccessibilityNodeInfo.AccessibilityAction action : selected.getActionList()) {
                writer.println("actionId=" + action.getId());
            }
        }
    }

    private final class FocusRing extends View {
        private final Paint paint = new Paint();
        private final Paint outline = new Paint(Paint.ANTI_ALIAS_FLAG);
        private Rect bounds;
        private float cursorX = -1;
        private float cursorY = -1;
        private boolean cursorPressed;
        private final Paint cursorPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint cursorGlowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path cursorShape = new Path();
        private int axisKey;
        private final Runnable repeat = new Runnable() {
            @Override public void run() {
                if (axisKey == 0) return;
                if ((axisKey==Direction.LEFT || axisKey==Direction.RIGHT)
                        && selected!=null && selected.getRangeInfo()!=null) {stopRepeat();return;}
                navigate(axisKey);
                handler.postDelayed(this, 160);
            }
        };

        FocusRing(Context context) {
            super(context);
            setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            setFocusableInTouchMode(true);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(Color.argb(20, 0, 0, 0));
            paint.setAntiAlias(true);
            outline.setStyle(Paint.Style.STROKE);outline.setStrokeWidth(3);
            outline.setColor(Color.rgb(0,150,136));
            // Trace the reference silhouette: upper-left tip, rounded wings,
            // and a shallow inset. (0, 0) is on the tip, not the shape's center.
            cursorShape.moveTo(0, 0);
            cursorShape.cubicTo(2, -2, 5, -2, 9, 0);
            cursorShape.lineTo(60, 27);
            cursorShape.cubicTo(66, 30, 65, 36, 58, 38);
            cursorShape.lineTo(36, 42);
            cursorShape.cubicTo(34, 42, 33, 43, 32, 46);
            cursorShape.lineTo(25, 65);
            cursorShape.cubicTo(23, 72, 16, 72, 14, 64);
            cursorShape.lineTo(-1, 9);
            cursorShape.cubicTo(-2, 5, -2, 2, 0, 0);
            cursorShape.close();
        }

        void stopRepeat() {
            axisKey = 0;
            handler.removeCallbacks(repeat);
        }

        @Override public void onWindowFocusChanged(boolean hasFocus) {
            super.onWindowFocusChanged(hasFocus);
            if(!hasFocus) {stopRepeat();held.clear();armedIdentity=null;armedKey=0;}
        }

        private void navigate(int key) {
            NavigationService.this.onKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, key));
            NavigationService.this.onKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, key));
        }

        @Override public boolean dispatchKeyEvent(KeyEvent event) {
            if (mouse != null && mouse.onKey(event)) return true;
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
            if (mouse != null && mouse.onMotion(event)) return true;
            if (event.isFromSource(InputDevice.SOURCE_JOYSTICK)
                    && event.getActionMasked()==MotionEvent.ACTION_CANCEL) {stopRepeat();return true;}
            if (event.isFromSource(InputDevice.SOURCE_JOYSTICK)
                    && event.getActionMasked() == MotionEvent.ACTION_MOVE) {
                float x = event.getAxisValue(MotionEvent.AXIS_HAT_X);
                float y = event.getAxisValue(MotionEvent.AXIS_HAT_Y);
                if (Math.abs(x) < 0.5f && Math.abs(y) < 0.5f) {
                    float[] stick = MouseController.sticks(event);
                    x = stick[0]; y = stick[1];
                }
                int key = x < -0.5f ? Direction.LEFT : x > 0.5f ? Direction.RIGHT
                        : y < -0.5f ? Direction.UP : y > 0.5f ? Direction.DOWN : 0;
                if (key != axisKey) {
                    stopRepeat();
                    axisKey = key;
                    if (key != 0) {
                        navigate(key);
                        if((key!=Direction.LEFT && key!=Direction.RIGHT)
                                || selected==null || selected.getRangeInfo()==null) handler.postDelayed(repeat, 400);
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

        void showCursor(float x, float y, boolean pressed) {
            cursorX = x;
            cursorY = y;
            cursorPressed = pressed;
            invalidate();
        }

        @Override protected void onDraw(Canvas canvas) {
            int[] location = new int[2];
            getLocationOnScreen(location);
            if (bounds != null) {
                Rect local = new Rect(bounds);
                local.offset(-location[0], -location[1]);
                canvas.drawRect(local, paint);
                canvas.drawRect(local, outline);
            }
            if (cursorX >= 0 && cursorY >= 0) {
                float x = cursorX - location[0], y = cursorY - location[1];
                // About 33 x 36 physical pixels on a 480-pixel short edge.
                float s = 0.5f * Math.max(0.8f, Math.min(1.5f,
                        Math.min(getWidth(), getHeight()) / 480f));
                int save = canvas.save();
                canvas.translate(x, y);
                canvas.scale(s, s);

                int fill = cursorPressed ? 0xff42e3d4 : Color.WHITE;
                cursorGlowPaint.setStyle(Paint.Style.FILL);
                cursorGlowPaint.setColor(fill);
                cursorGlowPaint.setShadowLayer(cursorPressed ? 8 : 5,
                        0, cursorPressed ? 0 : 2, cursorPressed ? 0x8835d9cb : 0x55000000);
                canvas.drawPath(cursorShape, cursorGlowPaint);
                cursorGlowPaint.clearShadowLayer();
                cursorPaint.setStyle(Paint.Style.FILL);
                cursorPaint.setColor(fill);
                canvas.drawPath(cursorShape, cursorPaint);
                canvas.restoreToCount(save);
            }
        }
    }
}
