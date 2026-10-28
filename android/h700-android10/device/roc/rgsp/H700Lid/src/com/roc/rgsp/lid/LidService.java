package com.roc.rgsp.lid;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.PrintWriter;
import java.lang.reflect.Method;

/** Explicit RG34XXSP profile only; no input injection, LCD writes or wake locks. */
public final class LidService extends Service {
    private static final String TAG = "H700Lid";
    private static final String CHANNEL = "lid";
    private static final File SENSOR = new File(
            "/sys/class/power_supply/axp2202-battery/hallkey");
    private static final long POLL_MS = 250, DEBOUNCE_MS = 250;
    private Handler handler;
    private PowerManager power;
    private Method sleep, wake;
    private int sleepReason, wakeReason;
    private volatile boolean fixture;
    private volatile int lastSample = -1, sleeps, wakes, readErrors, powerErrors;
    private volatile LidState state;
    private File sensor;
    private long fixtureDeadline, nextErrorLog;

    private static String property(String key) {
        try {
            return (String) Class.forName("android.os.SystemProperties")
                    .getMethod("get", String.class, String.class).invoke(null, key, "");
        } catch (ReflectiveOperationException e) { return ""; }
    }

    static boolean supported() {
        return "rgsp".equals(property("ro.product.device"))
                && "rg34xxsp".equals(property("persist.vendor.rgsp.input_profile"))
                && SENSOR.canRead();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences("lid", MODE_PRIVATE);
    }

    static boolean enabled(Context context) { return prefs(context).getBoolean("enabled", true); }

    @Override public void onCreate() {
        super.onCreate();
        power = (PowerManager) getSystemService(POWER_SERVICE);
        // Lifecycle and polling share one queue: mode changes cannot race an old
        // sensor callback into issuing a second power action.
        handler = new Handler(Looper.getMainLooper());
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? "" : intent.getAction();
        handler.removeCallbacksAndMessages(null);
        if ("com.roc.rgsp.lid.DISABLE".equals(action)) {
            prefs(this).edit().putBoolean("enabled", false).commit();
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        fixture = "com.roc.rgsp.lid.TEST".equals(action);
        if (!supported() || (fixture && !"1".equals(property("ro.debuggable")))) {
            Log.e(TAG, "Refuse unsupported profile or non-debug fixture");
            stopSelf();
            return START_NOT_STICKY;
        }
        if ("com.roc.rgsp.lid.ENABLE".equals(action)) {
            prefs(this).edit().putBoolean("enabled", true).commit();
        }
        if (!fixture && !enabled(this)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        try {
            // The same methods and reasons used by Android 10's power-button policy.
            // Reflection permits the isolated SDK29 build; platform signing grants
            // DEVICE_POWER and trusted access. Refuse activation if APIs differ.
            sleep = PowerManager.class.getMethod("goToSleep", long.class, int.class, int.class);
            wake = PowerManager.class.getMethod("wakeUp", long.class, int.class, String.class);
            sleepReason = PowerManager.class.getField("GO_TO_SLEEP_REASON_POWER_BUTTON").getInt(null);
            wakeReason = PowerManager.class.getField("WAKE_REASON_POWER_BUTTON").getInt(null);
            sensor = SENSOR;
            if (fixture) {
                sensor = new File(getFilesDir(), "lid-test-state");
                try (FileOutputStream out = new FileOutputStream(sensor, false)) {
                    out.write(new byte[] {'1', '\n'});
                }
                fixtureDeadline = SystemClock.elapsedRealtime() + 120000;
            }
            NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            manager.createNotificationChannel(new NotificationChannel(CHANNEL,
                    "合盖控制", NotificationManager.IMPORTANCE_LOW));
            startForeground(1, new Notification.Builder(this, CHANNEL)
                    .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
                    .setContentTitle("合盖息屏，开盖唤醒")
                    .setContentText(fixture ? "受控测试，120 秒后停止" : "RG34XXSP 屏幕开合控制")
                    .setOngoing(true).build());
            state = new LidState(DEBOUNCE_MS);
            Log.i(TAG, "START mode=" + (fixture ? "fixture" : "sensor")
                    + " sleepReason=" + sleepReason + " wakeReason=" + wakeReason);
            handler.post(poll);
            return fixture ? START_NOT_STICKY : START_STICKY;
        } catch (Exception e) {
            Log.e(TAG, "Cannot activate lid control", e);
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
    }

    private static int sample(File file) {
        try (FileReader reader = new FileReader(file)) {
            char[] text = new char[16];
            int count = reader.read(text);
            String value = count <= 0 ? "" : new String(text, 0, count).trim();
            return "0".equals(value) ? 0 : "1".equals(value) ? 1 : -1;
        } catch (Exception e) { return -1; }
    }

    private final Runnable poll = new Runnable() {
        @Override public void run() {
            long now = SystemClock.elapsedRealtime();
            if (fixture && now >= fixtureDeadline) {
                Log.i(TAG, "Fixture deadline; stop without changing persistent enable preference");
                stopForeground(true);
                stopSelf();
                return;
            }
            lastSample = sample(sensor);
            if (lastSample < 0) {
                readErrors++;
                if (now >= nextErrorLog) {
                    Log.w(TAG, "Invalid/unavailable hall sample; no power action");
                    nextErrorLog = now + 60000;
                }
            }
            LidState.Action action = state.observe(lastSample, now, power.isInteractive());
            try {
                if (action == LidState.Action.SLEEP) {
                    sleep.invoke(power, SystemClock.uptimeMillis(), sleepReason, 0);
                    sleeps++;
                    Log.i(TAG, "CLOSE -> power-button sleep");
                } else if (action == LidState.Action.WAKE) {
                    wake.invoke(power, SystemClock.uptimeMillis(), wakeReason, "H700Lid:OPEN");
                    wakes++;
                    Log.i(TAG, "OPEN -> power-button wake");
                }
            } catch (Exception e) {
                // Never retry a failed transition as a repeating toggle.
                powerErrors++;
                Log.e(TAG, "Power transition failed", e);
            }
            handler.postDelayed(this, POLL_MS);
        }
    };

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        stopForeground(true);
        super.onDestroy();
    }

    @Override protected void dump(FileDescriptor fd, PrintWriter out, String[] args) {
        out.println("profileSupported=" + supported() + " enabled=" + enabled(this));
        out.println("mode=" + (fixture ? "fixture" : "sensor") + " sample=" + lastSample
                + " stable=" + (state == null ? -1 : state.stable()));
        out.println("sleeps=" + sleeps + " wakes=" + wakes + " readErrors=" + readErrors
                + " powerErrors=" + powerErrors);
        out.println("pollMs=" + POLL_MS + " debounceMs=" + DEBOUNCE_MS + " holdsWakeLock=false");
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
