package com.roc.rgsp.rotation;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public final class RotationReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        boolean prepare = "com.roc.rgsp.rotation.PREPARE".equals(action);
        if (!prepare && !Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)) return;
        PendingResult result = goAsync();
        WindowBridge.SERIAL.execute(() -> {
            try {
                if (prepare) WindowBridge.prepare(context); else WindowBridge.boot(context);
            } catch (Exception e) { Log.e(WindowBridge.TAG, "Rotation initialization failed", e); }
            finally { result.finish(); }
        });
    }
}
