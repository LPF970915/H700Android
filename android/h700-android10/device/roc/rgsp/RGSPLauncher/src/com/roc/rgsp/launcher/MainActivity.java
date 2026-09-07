package com.roc.rgsp.launcher;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

public class MainActivity extends Activity {
    private HomeView home;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().setNavigationBarColor(Color.BLACK);
        getWindow().setStatusBarColor(Color.BLACK);
        hideSystemUi();
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE);
        home = new HomeView(this, loadApps());
        setContentView(home);
    }

    @Override
    public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) hideSystemUi();
    }

    private void hideSystemUi() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    private List<AppEntry> loadApps() {
        Intent query = new Intent(Intent.ACTION_MAIN);
        query.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> resolved = getPackageManager().queryIntentActivities(query, 0);
        List<AppEntry> result = new ArrayList<>();
        for (ResolveInfo info : resolved) {
            String pkg = info.activityInfo.packageName;
            if (pkg.equals(getPackageName()) || pkg.equals("com.android.launcher3")
                    || pkg.equals("com.overdevs.at4k")) continue;
            CharSequence label = info.loadLabel(getPackageManager());
            result.add(new AppEntry(label == null ? pkg : label.toString(),
                    info.activityInfo.packageName, info.activityInfo.name,
                    info.loadIcon(getPackageManager())));
        }
        Collections.sort(result, new Comparator<AppEntry>() {
            @Override public int compare(AppEntry a, AppEntry b) {
                return a.label.compareToIgnoreCase(b.label);
            }
        });
        return result;
    }

    public void launch(String packageName, String activityName) {
        try {
            Intent intent = new Intent(Intent.ACTION_MAIN);
            intent.addCategory(Intent.CATEGORY_LAUNCHER);
            intent.setClassName(packageName, activityName);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        } catch (RuntimeException ignored) {
            home.invalidate();
        }
    }

    public void openSettings() {
        try {
            startActivity(new Intent(Settings.ACTION_SETTINGS));
        } catch (RuntimeException ignored) {
            home.invalidate();
        }
    }

    public void openFiles() {
        try {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            startActivity(intent);
        } catch (RuntimeException ignored) {
            home.invalidate();
        }
    }

    public void openAt4k() {
        launch("com.overdevs.at4k", "com.overdevs.at4k.MainActivity");
    }

    public static final class AppEntry {
        public final String label;
        public final String packageName;
        public final String activityName;
        public final android.graphics.drawable.Drawable icon;

        AppEntry(String label, String packageName, String activityName,
                 android.graphics.drawable.Drawable icon) {
            this.label = label;
            this.packageName = packageName;
            this.activityName = activityName;
            this.icon = icon;
        }
    }
}
