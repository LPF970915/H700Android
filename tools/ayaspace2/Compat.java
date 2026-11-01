package com.roc.h700.ayaspace;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Point;
import android.graphics.Rect;
import android.os.Environment;
import android.os.storage.StorageVolume;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.view.WindowInsets;
import android.view.KeyEvent;
import android.view.inputmethod.InputMethodManager;
import java.io.File;

/** API29 storage and display adapters; no system UID or platform signature. */
public final class Compat {
    private static Context context;
    public static void init(Context value) {
        context = value.getApplicationContext();
        if (value instanceof Activity) ((Activity)value).requestWindowFeature(Window.FEATURE_NO_TITLE);
    }
    public static boolean isH700() {
        if (android.os.Build.VERSION.SDK_INT != 29) return false;
        if ("RGSP H700".equals(android.os.Build.MODEL)
            && "sun50iw9p1".equals(android.os.Build.HARDWARE)) return true;
        try {
            Object profile = Class.forName("android.os.SystemProperties").getMethod("get", String.class)
                .invoke(null, "persist.vendor.rgsp.input_profile");
            return "rg34xxsp".equals(profile);
        } catch (ReflectiveOperationException failure) { return false; }
    }
    public static boolean storageAllowed() {
        return context != null
            && context.checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED
            && context.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
    }
    public static void requestStorage(Activity activity) {
        if (!storageAllowed()) activity.requestPermissions(new String[] {
            Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE
        }, 0x504d04);
    }
    public static File volumeDirectory(StorageVolume volume) {
        if (volume.isPrimary()) return Environment.getExternalStorageDirectory();
        String uuid = volume.getUuid();
        return uuid == null ? null : new File("/storage", uuid);
    }
    public static Rect screenBounds(WindowManager manager) {
        Point size = new Point();
        manager.getDefaultDisplay().getRealSize(size);
        return new Rect(0, 0, size.x, size.y);
    }
    public static void decorFits(Window window, boolean fits) {
        View view = window.getDecorView();
        int mask = View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;
        int flags = view.getSystemUiVisibility();
        view.setSystemUiVisibility(fits ? flags & ~mask : flags | mask);
    }
    public static void immersive(Window window, boolean enabled) {
        View view = window.getDecorView();
        int mask = View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
        int flags = view.getSystemUiVisibility();
        view.setSystemUiVisibility(enabled ? flags | mask : flags & ~mask);
    }
    public static void appearance(Activity activity) {
        Window window = activity.getWindow();
        window.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        if (activity.getActionBar() != null) activity.getActionBar().hide();
        decorFits(window, false);
        immersive(window, true);
        window.setStatusBarColor(0);
        window.setNavigationBarColor(0);
    }
    public static void lightBar(Window window, boolean light, boolean status) {
        View view = window.getDecorView();
        int mask = status ? View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR : View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        int flags = view.getSystemUiVisibility();
        view.setSystemUiVisibility(light ? flags | mask : flags & ~mask);
    }
    public static WindowInsets emptyInsets() {
        return new WindowInsets.Builder().build().consumeSystemWindowInsets().consumeStableInsets().consumeDisplayCutout();
    }
    public static void show(Window window, int types) {
        if ((types & 7) != 0) immersive(window, false);
        if ((types & 8) != 0) {
            View focus = window.getDecorView().findFocus();
            if (focus != null) ((InputMethodManager) window.getContext().getSystemService(Context.INPUT_METHOD_SERVICE))
                .showSoftInput(focus, 0);
        }
    }
    public static void observeKeyboard(final View view) {
        view.getViewTreeObserver().addOnGlobalLayoutListener(new android.view.ViewTreeObserver.OnGlobalLayoutListener() {
            private int previous = -1;
            public void onGlobalLayout() {
                Rect frame = new Rect();
                view.getWindowVisibleDisplayFrame(frame);
                int screen = view.getRootView().getHeight();
                int bottom = Math.max(0, screen - frame.bottom - view.getRootView().getPaddingBottom());
                if (bottom < screen / 5) bottom = 0;
                if (bottom == previous) return;
                previous = bottom;
                try {
                    Class.forName("org.godotengine.godot.GodotLib").getMethod("setVirtualKeyboardHeight", int.class).invoke(null, bottom);
                } catch (ReflectiveOperationException failure) {
                    android.util.Log.w("H700-Ayaspace", "Keyboard height adapter unavailable", failure);
                }
            }
        });
    }
    public static void execSql(SQLiteDatabase database, String sql, Object[] values) {
        String filename = "INSERT INTO identification_history(rom_file_id, filename_game_id) VALUES (?, ?) ON CONFLICT(rom_file_id) DO UPDATE SET filename_game_id=excluded.filename_game_id WHERE filename_promoted=0";
        String content = "INSERT INTO identification_history(rom_file_id, content_exact_seen) VALUES (?, 1) ON CONFLICT(rom_file_id) DO UPDATE SET content_exact_seen=1";
        boolean nameUpdate = filename.equals(sql);
        if (!nameUpdate && !content.equals(sql)) { database.execSQL(sql, values); return; }
        boolean ownTransaction = !database.inTransaction();
        if (ownTransaction) database.beginTransaction();
        try {
            database.execSQL(nameUpdate
                ? "INSERT OR IGNORE INTO identification_history(rom_file_id, filename_game_id) VALUES (?, ?)"
                : "INSERT OR IGNORE INTO identification_history(rom_file_id, content_exact_seen) VALUES (?, 1)", values);
            if (nameUpdate) database.execSQL("UPDATE identification_history SET filename_game_id=? WHERE rom_file_id=? AND filename_promoted=0", new Object[] { values[1], values[0] });
            else database.execSQL("UPDATE identification_history SET content_exact_seen=1 WHERE rom_file_id=?", values);
            if (ownTransaction) database.setTransactionSuccessful();
        } finally { if (ownTransaction) database.endTransaction(); }
    }
    private static KeyEvent remap(KeyEvent event) {
        if (event.getDevice() == null || !"ANBERNIC-keys".equals(event.getDevice().getName())) return event;
        int key = event.getKeyCode();
        switch (event.getScanCode()) {
            case 304: key = KeyEvent.KEYCODE_BUTTON_A; break;
        }
        if (key == event.getKeyCode()) return event;
        return new KeyEvent(event.getDownTime(), event.getEventTime(), event.getAction(), key,
            event.getRepeatCount(), event.getMetaState(), event.getDeviceId(), event.getScanCode(),
            event.getFlags(), event.getSource());
    }
    public static KeyEvent remapGodot(KeyEvent event) { return remap(event); }
    private static boolean selectHeld;
    private static long selectDown;
    private static boolean menuChord;
    public static KeyEvent remapPlay(KeyEvent event) {
        if (event.getDevice() != null && "ANBERNIC-keys".equals(event.getDevice().getName())) {
            if (event.getScanCode() == 310) {
                selectHeld = event.getAction() == KeyEvent.ACTION_DOWN;
                if (selectHeld && event.getRepeatCount() == 0) selectDown = event.getEventTime();
            }
            if (event.getScanCode() == 311) {
                if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0)
                    menuChord = selectHeld && event.getEventTime() - selectDown < 1500;
                if (menuChord) {
                    if (event.getAction() == KeyEvent.ACTION_UP) menuChord = false;
                    return new KeyEvent(event.getDownTime(), event.getEventTime(), event.getAction(), KeyEvent.KEYCODE_BACK,
                        event.getRepeatCount(), event.getMetaState(), event.getDeviceId(), event.getScanCode(),
                        event.getFlags(), event.getSource());
                }
            }
        }
        return remap(event);
    }
}
