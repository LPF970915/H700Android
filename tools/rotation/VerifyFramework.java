import android.graphics.Rect;
import android.content.res.Configuration;

/** Load/link the candidate in a separate ART process before replacing services.jar. */
public final class VerifyFramework {
    public static void main(String[] args) throws Exception {
        ClassLoader loader = VerifyFramework.class.getClassLoader();
        Class<?> record = Class.forName("com.android.server.wm.ActivityRecord", false, loader);
        record.getDeclaredMethod("h700ForceLandscape");
        record.getDeclaredMethod("getRequestedConfigurationOrientation");
        record.getDeclaredMethod("shouldUseSizeCompatMode");
        record.getDeclaredMethod("computeBounds", Rect.class, Rect.class);
        record.getDeclaredMethod("resolveOverrideConfiguration", Configuration.class);
        record.getDeclaredField("mCompatDisplayInsets");
        Class<?> display = Class.forName("com.android.server.wm.ActivityDisplay", false, loader);
        display.getDeclaredField("mDisplayId");
        display.getDeclaredField("mDisplayContent");
        Class.forName("com.android.server.wm.DisplayContent", false, loader).getDeclaredMethod("getDisplayRotation");
        Class.forName("com.android.server.wm.DisplayRotation", false, loader).getDeclaredMethod("isFixedToUserRotation");
        System.out.println("H700_ROTATION_ART_LINK_PASS methods=" + record.getDeclaredMethods().length);
    }
}
