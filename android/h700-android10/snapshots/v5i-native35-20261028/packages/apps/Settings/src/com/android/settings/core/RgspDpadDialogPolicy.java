package com.android.settings.core;

import android.app.Dialog;
import android.content.res.Configuration;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import androidx.fragment.app.DialogFragment;
import androidx.fragment.app.Fragment;

/** Keep the active field visible when a TV keyboard occupies a small landscape screen. */
final class RgspDpadDialogPolicy {
    static void apply(Fragment fragment) {
        if (!(fragment instanceof DialogFragment)) return;
        Dialog dialog = ((DialogFragment) fragment).getDialog();
        Window window = dialog == null ? null : dialog.getWindow();
        if (window == null) return;
        configurePickerHeaders(window.getDecorView());
        Configuration configuration = fragment.getResources().getConfiguration();
        if (configuration.orientation != Configuration.ORIENTATION_LANDSCAPE
                || configuration.screenHeightDp >= 420) return;
        // The BSP renderer paints adjacent calendar pages over the header.
        // Rasterize only this small pager inside its own bounds; keep native
        // date selection and its virtual accessibility actions unchanged.
        int pagerId = fragment.getResources().getIdentifier(
                "day_picker_view_pager", "id", "android");
        View pager = pagerId == 0 ? null : window.getDecorView().findViewById(pagerId);
        if (pager instanceof ViewGroup) {
            ((ViewGroup) pager).setClipChildren(true);
            ((ViewGroup) pager).setClipToPadding(true);
            pager.setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        }
        if (!hasEditor(window.getDecorView())) return;
        int mode = window.getAttributes().softInputMode;
        int adjust = mode & WindowManager.LayoutParams.SOFT_INPUT_MASK_ADJUST;
        if (adjust == WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
                || adjust == WindowManager.LayoutParams.SOFT_INPUT_ADJUST_UNSPECIFIED) {
            window.setSoftInputMode((mode & ~WindowManager.LayoutParams.SOFT_INPUT_MASK_ADJUST)
                    | WindowManager.LayoutParams.SOFT_INPUT_ADJUST_PAN);
        }
    }

    private static void configurePickerHeaders(View view) {
        // NumericTextView uses input focus for direct digit entry and restores
        // its old value on blur. Remote navigation uses its native click to
        // choose a dial; direct entry remains available in the text-input mode.
        if ("com.android.internal.widget.NumericTextView".equals(view.getClass().getName())
                && view.isClickable() && !view.onCheckIsTextEditor()) {
            view.setFocusableInTouchMode(false);
            view.setFocusable(false);
        }
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                configurePickerHeaders(group.getChildAt(i));
            }
        }
    }

    private static boolean hasEditor(View view) {
        if (view.onCheckIsTextEditor()) return true;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                if (hasEditor(group.getChildAt(i))) return true;
            }
        }
        return false;
    }
}
