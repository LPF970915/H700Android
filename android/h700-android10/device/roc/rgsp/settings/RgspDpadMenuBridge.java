package com.android.settings.core;

import android.view.Menu;
import android.view.MenuItem;
import android.widget.Toolbar;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentActivity;
import androidx.fragment.app.FragmentManager;
import java.util.ArrayList;
import java.util.List;

/** Complete an empty framework Toolbar from the currently resumed support fragments. */
final class RgspDpadMenuBridge {
    private final FragmentActivity activity;
    private final Toolbar toolbar;
    private boolean ownsMenu;
    private final Runnable refresh = this::populateIfMissing;
    private final FragmentManager.FragmentLifecycleCallbacks callbacks =
            new FragmentManager.FragmentLifecycleCallbacks() {
        @Override public void onFragmentResumed(FragmentManager manager, Fragment fragment) {
            RgspDpadDialogPolicy.apply(fragment);
            schedule();
        }
    };

    RgspDpadMenuBridge(FragmentActivity activity, Toolbar toolbar) {
        this.activity = activity;
        this.toolbar = toolbar;
        activity.getSupportFragmentManager().registerFragmentLifecycleCallbacks(callbacks, true);
    }

    void schedule() {
        toolbar.removeCallbacks(refresh);
        toolbar.postDelayed(refresh, 250);
    }

    void pause() { toolbar.removeCallbacks(refresh); }

    void close() {
        pause();
        activity.getSupportFragmentManager().unregisterFragmentLifecycleCallbacks(callbacks);
    }

    private void collect(FragmentManager manager, List<Fragment> result) {
        for (Fragment fragment : manager.getFragments()) {
            if (!fragment.isAdded() || fragment.isHidden() || !fragment.isResumed()
                    || !fragment.isMenuVisible()) continue;
            if (fragment.hasOptionsMenu()) result.add(fragment);
            collect(fragment.getChildFragmentManager(), result);
        }
    }

    private List<Fragment> visibleMenus() {
        List<Fragment> result = new ArrayList<>();
        collect(activity.getSupportFragmentManager(), result);
        return result;
    }

    private void populateIfMissing() {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        Menu menu = toolbar.getMenu();
        if (!ownsMenu && menu.size() != 0) return;
        if (ownsMenu) menu.clear();
        List<Fragment> fragments = visibleMenus();
        for (Fragment fragment : fragments) {
            fragment.onCreateOptionsMenu(menu, activity.getMenuInflater());
            fragment.onPrepareOptionsMenu(menu);
        }
        ownsMenu = menu.size() != 0;
        if (ownsMenu) toolbar.setOnMenuItemClickListener(this::selected);
    }

    private boolean selected(MenuItem item) {
        for (Fragment fragment : visibleMenus()) {
            if (fragment.onOptionsItemSelected(item)) return true;
        }
        return activity.onOptionsItemSelected(item);
    }
}
