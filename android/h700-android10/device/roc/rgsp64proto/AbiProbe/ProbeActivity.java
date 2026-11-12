package com.roc.h700.abiprobe;

import android.app.Activity;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.os.Process;
import android.util.Log;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** ARM64-only APK acceptance sentinel. Never included in the release preinstall list. */
public final class ProbeActivity extends Activity {
    static { System.loadLibrary("h700_abi_probe"); }
    private static native int pointerBits();
    private GLSurfaceView surface;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        int bits = pointerBits();
        boolean pass = bits == 64 && Process.is64Bit();
        Log.i("H700AbiProbe", "ART64_JNI=" + pass + " pointer_bits=" + bits);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        TextView title = new TextView(this);
        title.setTextSize(16);
        title.setText("H700 ABI Probe: " + bits + " bit / ART64=" + Process.is64Bit());
        root.addView(title);
        surface = new GLSurfaceView(this);
        surface.setEGLContextClientVersion(2);
        surface.setRenderer(new GLSurfaceView.Renderer() {
            public void onSurfaceCreated(GL10 unused, EGLConfig config) {
                Log.i("H700AbiProbe", "RENDERER=" + GLES20.glGetString(GLES20.GL_RENDERER));
            }
            public void onSurfaceChanged(GL10 unused, int width, int height) {
                GLES20.glViewport(0, 0, width, height);
            }
            public void onDrawFrame(GL10 unused) {
                GLES20.glClearColor(0.05f, 0.75f, 0.15f, 1);
                GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);
            }
        });
        surface.setRenderMode(GLSurfaceView.RENDERMODE_WHEN_DIRTY);
        root.addView(surface, new LinearLayout.LayoutParams(-1, 0, 1));
        Button close = new Button(this);
        close.setText("返回 / Close"); close.setTextSize(16);
        close.setOnClickListener(view -> finish());
        root.addView(close); setContentView(root); close.requestFocus();
        if (!pass) title.append(" — FAIL");
    }
    @Override protected void onResume() { super.onResume(); surface.onResume(); }
    @Override protected void onPause() { surface.onPause(); super.onPause(); }
}
