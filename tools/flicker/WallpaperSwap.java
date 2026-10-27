import android.app.WallpaperManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import java.io.FileOutputStream;

/**
 * Safe wallpaper experiment helper.
 * Run with: app_process /system/bin WallpaperSwap backup <png> | set | clear
 */
public class WallpaperSwap {
    private static Context systemContext() throws Exception {
        Class<?> at = Class.forName("android.app.ActivityThread");
        Object thread = at.getMethod("systemMain").invoke(null);
        return (Context) at.getMethod("getSystemContext").invoke(thread);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.out.println("usage: backup <png> | set | clear");
            return;
        }
        Context ctx = systemContext();
        WallpaperManager wm = WallpaperManager.getInstance(ctx);
        String op = args[0];
        if ("backup".equals(op)) {
            Drawable d = wm.getDrawable();
            Bitmap b = Bitmap.createBitmap(720, 480, Bitmap.Config.ARGB_8888);
            Canvas bc = new Canvas(b);
            d.setBounds(0, 0, 720, 480);
            d.draw(bc);
            FileOutputStream out = new FileOutputStream(args[1]);
            b.compress(Bitmap.CompressFormat.PNG, 100, out);
            out.close();
            System.out.println("BACKUP " + b.getWidth() + "x" + b.getHeight());
        } else if ("set".equals(op)) {
            Bitmap b = Bitmap.createBitmap(720, 480, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(b);
            canvas.drawColor(Color.rgb(32, 64, 96));
            wm.setBitmap(b, null, true);
            System.out.println("SET 720x480");
        } else if ("clear".equals(op)) {
            wm.clear();
            System.out.println("CLEARED");
        } else {
            System.out.println("unknown op " + op);
        }
    }
}
