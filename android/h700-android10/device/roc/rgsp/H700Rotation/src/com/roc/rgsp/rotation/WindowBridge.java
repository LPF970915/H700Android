package com.roc.rgsp.rotation;

import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.IBinder;
import android.os.Process;
import android.os.ResultReceiver;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

final class WindowBridge {
    static final String KEY = "h700_force_landscape";
    static final String TAG = "H700Rotation";
    static final ExecutorService SERIAL = Executors.newSingleThreadExecutor();

    static boolean supported() {
        try {
            return Process.myUid() / 100000 == 0 && "rgsp".equals(Class.forName("android.os.SystemProperties")
                    .getMethod("get", String.class).invoke(null, "ro.product.device"))
                    && !"1".equals(Class.forName("android.os.SystemProperties")
                    .getMethod("get", String.class, String.class)
                    .invoke(null, "persist.sys.h700.rotation_safe_mode", "0"));
        } catch (Exception e) { return false; }
    }
    static Context storage(Context context) { return context.createDeviceProtectedStorageContext(); }
    static SharedPreferences prefs(Context c) { return storage(c).getSharedPreferences("rotation", Context.MODE_PRIVATE); }
    static boolean desired(Context c) { return Settings.Secure.getInt(c.getContentResolver(), KEY, 1) != 0; }
    static IBinder service(String name) throws Exception {
        IBinder binder = (IBinder) Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class).invoke(null, name);
        if (binder == null) throw new IllegalStateException("Service unavailable: " + name);
        return binder;
    }
    static String windowDump(Context context) throws Exception {
        File file = File.createTempFile("rotation-dump-", ".txt", storage(context).getCacheDir());
        try (FileOutputStream out = new FileOutputStream(file)) {
            service("window").dump(out.getFD(), new String[] {"displays"});
            return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        } finally { file.delete(); }
    }
    static void command(Context context, String... args) throws Exception {
        // Only fixed internal command arrays are passed here; no exported arbitrary-command API.
        File file = File.createTempFile("rotation-command-", ".txt", storage(context).getCacheDir());
        CountDownLatch done = new CountDownLatch(1);
        AtomicInteger result = new AtomicInteger(-1);
        ResultReceiver receiver = new ResultReceiver(null) {
            @Override protected void onReceiveResult(int code, Bundle data) { result.set(code); done.countDown(); }
        };
        try (FileInputStream in = new FileInputStream("/dev/null"); FileOutputStream out = new FileOutputStream(file)) {
            Class<?> callback = Class.forName("android.os.ShellCallback");
            IBinder.class.getMethod("shellCommand", FileDescriptor.class, FileDescriptor.class,
                    FileDescriptor.class, String[].class, callback, ResultReceiver.class)
                    .invoke(service("window"), in.getFD(), out.getFD(), out.getFD(), args, null, receiver);
            if (!done.await(4, TimeUnit.SECONDS) || result.get() != 0) {
                throw new IllegalStateException("Window command failed: " + result.get());
            }
        } finally { file.delete(); }
    }
    private static void snapshot(Context c) throws Exception {
        SharedPreferences p = prefs(c);
        if (p.getBoolean("saved", false)) return;
        boolean saved = p.edit().putInt("auto", Settings.System.getInt(c.getContentResolver(),
                        Settings.System.ACCELEROMETER_ROTATION, 0))
                .putInt("rotation", Settings.System.getInt(c.getContentResolver(), Settings.System.USER_ROTATION, 0))
                .putBoolean("fixed", RotationState.fixed(windowDump(c))).putBoolean("saved", true).commit();
        if (!saved) throw new IllegalStateException("Cannot save rotation rollback state");
    }
    private static void restore(Context c) throws Exception {
        SharedPreferences p = prefs(c);
        if (!p.getBoolean("saved", false)) return;
        command(c, "set-fix-to-user-rotation", "-d", "0", p.getBoolean("fixed", false) ? "enabled" : "disabled");
        command(c, "set-user-rotation", "lock", "-d", "0", Integer.toString(p.getInt("rotation", 0)));
        if (p.getInt("auto", 0) != 0) command(c, "set-user-rotation", "free", "-d", "0");
    }
    static void apply(Context c, boolean enable) throws Exception {
        if (!supported()) throw new IllegalStateException("Unsupported product or user");
        if (enable) snapshot(c);
        try {
            if (enable) {
                command(c, "set-fix-to-user-rotation", "-d", "0", "enabled");
                command(c, "set-user-rotation", "lock", "-d", "0", "0");
                if (!RotationState.applied(windowDump(c))) throw new IllegalStateException("Rotation state did not apply");
            } else restore(c);
            if (!Settings.Secure.putInt(c.getContentResolver(), KEY, enable ? 1 : 0)) {
                throw new IllegalStateException("Cannot persist rotation preference");
            }
            if (!enable) prefs(c).edit().remove("saved").commit();
            Log.i(TAG, enable ? "FORCE_LANDSCAPE_ON" : "RESTORE_APP_ORIENTATION");
        } catch (Exception error) {
            if (enable) {
                try { restore(c); } catch (Exception rollback) { Log.e(TAG, "Rotation rollback failed", rollback); }
            }
            throw error;
        }
    }
    static void seedTile(Context c) throws Exception {
        SharedPreferences p = prefs(c);
        if (p.getBoolean("tileSeeded", false)) return;
        ComponentName component = new ComponentName(c, LandscapeTile.class);
        if (!hasTile(c, component)) {
            Object bar = Class.forName("com.android.internal.statusbar.IStatusBarService$Stub")
                    .getMethod("asInterface", IBinder.class).invoke(null, service("statusbar"));
            Class.forName("com.android.internal.statusbar.IStatusBarService")
                    .getMethod("addTile", ComponentName.class).invoke(bar, component);
        }
        for (int n = 0; n < 5; n++) {
            if (hasTile(c, component)) { p.edit().putBoolean("tileSeeded", true).commit(); return; }
            Thread.sleep(100);
        }
        // SystemUI can be unavailable early in boot. BOOT_COMPLETED retries after locked boot.
        Log.i(TAG, "Tile seed pending SystemUI");
    }
    private static boolean hasTile(Context c, ComponentName name) {
        return RotationState.hasTile(Settings.Secure.getString(c.getContentResolver(), "sysui_qs_tiles"),
                name.flattenToShortString(), name.flattenToString());
    }
    static void prepare(Context c) throws Exception {
        if (!supported()) return;
        snapshot(c);
        if (Settings.Secure.getString(c.getContentResolver(), KEY) == null) {
            Settings.Secure.putInt(c.getContentResolver(), KEY, 1);
        }
        seedTile(c);
    }
    static void boot(Context c) throws Exception {
        if (!supported()) return;
        apply(c, desired(c));
        seedTile(c);
    }
}
