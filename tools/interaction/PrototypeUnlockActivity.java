package com.roc.rgsp.navtrial;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.InputDevice;
import android.view.KeyEvent;
import java.io.File;

/** Prototype-only bridge for the GSI swipe lock; credential entry is unchanged. */
public final class PrototypeUnlockActivity extends Activity {
    static boolean prototype() {
        return "rgsp".equals(Build.DEVICE)
                && new File("/system/etc/h700-prototype/boot-entry-revision").isFile();
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        KeyguardManager manager = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (!prototype() || manager == null || manager.isDeviceSecure()) {
            finish();
            return;
        }
        setShowWhenLocked(true);
        new Handler(Looper.getMainLooper()).postDelayed(() -> finish(), 3000);
        manager.requestDismissKeyguard(this, new KeyguardManager.KeyguardDismissCallback() {
            @Override public void onDismissSucceeded() {
                Log.i("H700Unlock", "A swipe-lock dismissal succeeded");
                finish();
            }
            @Override public void onDismissCancelled() { finish(); }
            @Override public void onDismissError() {
                Log.w("H700Unlock", "Swipe-lock dismissal rejected");
                finish();
            }
        });
    }
}

final class PrototypeUnlock {
    private int armedDevice = Integer.MIN_VALUE;
    private long armedDownTime;

    boolean handle(Context context, KeyEvent event, boolean allowWindow) {
        InputDevice device = event.getDevice();
        KeyguardManager manager = (KeyguardManager) context.getSystemService(Context.KEYGUARD_SERVICE);
        if (PrototypeUnlockActivity.prototype() && manager != null && !manager.isDeviceSecure()
                && android.provider.Settings.Global.getInt(context.getContentResolver(), "h700_interaction_trace", 0)==1
                && device != null && "ANBERNIC-keys".equals(device.getName())) {
            Log.i("H700PhysicalKey", "action="+event.getAction()+" key="+event.getKeyCode()
                    +" scan="+event.getScanCode()+" device="+event.getDeviceId()+" flags="+event.getFlags()
                    +" repeat="+event.getRepeatCount()+" down="+event.getDownTime()+" time="+event.getEventTime()
                    +" locked="+manager.isKeyguardLocked()+" allow="+allowWindow+" armed="+armedDevice+":"+armedDownTime);
        }
        boolean eligible = allowWindow && PrototypeUnlockActivity.prototype()
                && event.getKeyCode() == KeyEvent.KEYCODE_ENTER && event.getScanCode() == 304
                && device != null && "ANBERNIC-keys".equals(device.getName())
                && manager != null && manager.isKeyguardLocked() && !manager.isDeviceSecure();
        if (!eligible) {
            armedDevice = Integer.MIN_VALUE;
            return false;
        }
        if (event.getAction() == KeyEvent.ACTION_DOWN) {
            if (event.getRepeatCount() == 0) {
                armedDevice = event.getDeviceId();
                armedDownTime = event.getDownTime();
            }
            return true;
        }
        if (event.getAction() != KeyEvent.ACTION_UP) return false;
        boolean paired = armedDevice == event.getDeviceId()
                && armedDownTime == event.getDownTime();
        armedDevice = Integer.MIN_VALUE;
        if (paired && !event.isCanceled()) {
            Intent intent = new Intent(context, PrototypeUnlockActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_HISTORY
                    | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS);
            context.startActivity(intent);
        }
        return true;
    }
}
