package com.overdevs.at4k;

import android.app.WallpaperManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import java.io.InputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Keep the explicitly selected custom image on HOME and the native A-unlock screen. */
public final class RgspWallpaper {
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final ExecutorService WORK = Executors.newSingleThreadExecutor();
    private static Context context;
    private static SharedPreferences prefs;
    private static boolean installed;
    private static final SharedPreferences.OnSharedPreferenceChangeListener LISTENER = (p, key) -> {
        if ("mode".equals(key) || "custom_wallpaper_uri".equals(key)) schedule();
    };
    private static final Runnable SYNC = () -> WORK.execute(() -> sync());

    public static synchronized void install(Context activity) {
        if (!installed) {
            context = activity.getApplicationContext();
            prefs = context.getSharedPreferences("launcher_prefs", Context.MODE_PRIVATE);
            prefs.registerOnSharedPreferenceChangeListener(LISTENER);
            installed = true;
        }
        schedule();
    }

    private static void schedule() {
        MAIN.removeCallbacks(SYNC);
        MAIN.postDelayed(SYNC, 250);
    }

    private static void sync() {
        if (!"customi".equals(prefs.getString("mode", ""))) return;
        String uri = prefs.getString("custom_wallpaper_uri", "");
        if (uri.isEmpty()) return;
        WallpaperManager manager = WallpaperManager.getInstance(context);
        try {
            if (uri.equals(prefs.getString("rgsp_wallpaper_synced_uri", ""))
                    && manager.getWallpaperId(WallpaperManager.FLAG_SYSTEM) == prefs.getInt("rgsp_wallpaper_system_id", -1)
                    && manager.getWallpaperId(WallpaperManager.FLAG_LOCK) == prefs.getInt("rgsp_wallpaper_lock_id", -1)) return;
            try (InputStream source = context.getContentResolver().openInputStream(Uri.parse(uri))) {
                if (source == null) return;
                manager.setStream(source, null, true,
                        WallpaperManager.FLAG_SYSTEM | WallpaperManager.FLAG_LOCK);
            }
            prefs.edit().putString("rgsp_wallpaper_synced_uri", uri)
                    .putInt("rgsp_wallpaper_system_id", manager.getWallpaperId(WallpaperManager.FLAG_SYSTEM))
                    .putInt("rgsp_wallpaper_lock_id", manager.getWallpaperId(WallpaperManager.FLAG_LOCK)).apply();
            Log.i("RgspWallpaper", "Custom image applied to system and lock wallpaper");
        } catch (Exception failure) {
            // Keep the previous system wallpaper if a picker URI is unavailable.
            Log.w("RgspWallpaper", "Wallpaper sync failed: " + failure.getClass().getSimpleName());
        }
    }
}
