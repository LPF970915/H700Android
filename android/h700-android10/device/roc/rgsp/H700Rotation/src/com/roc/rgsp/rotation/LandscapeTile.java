package com.roc.rgsp.rotation;

import android.graphics.drawable.Icon;
import android.os.Handler;
import android.os.Looper;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;
import android.util.Log;
import android.widget.Toast;

public final class LandscapeTile extends TileService {
    private final Handler main = new Handler(Looper.getMainLooper());
    private void publish(boolean failed) {
        boolean active = false;
        try { active = WindowBridge.desired(this) && RotationState.applied(WindowBridge.windowDump(this)); }
        catch (Exception e) { failed = true; Log.e(WindowBridge.TAG, "Cannot read rotation state", e); }
        final int state = failed ? Tile.STATE_UNAVAILABLE : active ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE;
        final String subtitle = failed ? "切换失败" : active ? "已开启" : "跟随应用";
        main.post(() -> {
            Tile tile = getQsTile();
            if (tile == null) return;
            tile.setLabel("强制横屏");
            tile.setSubtitle(subtitle);
            tile.setIcon(Icon.createWithResource(this, R.drawable.ic_landscape));
            tile.setState(state);
            tile.updateTile();
        });
    }
    @Override public void onStartListening() { WindowBridge.SERIAL.execute(() -> publish(false)); }
    @Override public void onClick() {
        WindowBridge.SERIAL.execute(() -> {
            boolean failed = false;
            try { WindowBridge.apply(this, !WindowBridge.desired(this)); }
            catch (Exception e) {
                failed = true;
                Log.e(WindowBridge.TAG, "Tile switch failed", e);
                main.post(() -> Toast.makeText(this, "强制横屏切换失败", Toast.LENGTH_SHORT).show());
            }
            publish(failed);
        });
    }
}
