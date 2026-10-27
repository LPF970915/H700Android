package com.android.documentsui.base;

import android.app.AlertDialog;
import android.content.Context;
import android.content.res.Configuration;
import android.os.Build;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.KeyEvent;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

/** Shared controller-friendly file-name editor using the platform TV dialog. */
public final class RgspFileNameDialog {
    public interface Submit { boolean submit(String name); }
    public final EditText editor;
    public final AlertDialog dialog;
    public static boolean applies(Context context) { return "rgsp".equals(Build.DEVICE); }
    public static RgspFileNameDialog create(Context context, int title, int hint, Submit submit) {
        return new RgspFileNameDialog(context, title, hint, submit);
    }
    private RgspFileNameDialog(Context context, int title, int hint, Submit submit) {
        boolean night = (context.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        AlertDialog.Builder builder = new AlertDialog.Builder(context, night
                ? android.R.style.Theme_Material_Dialog_Alert
                : android.R.style.Theme_Material_Light_Dialog_Alert);
        Context themed = builder.getContext();
        float density = themed.getResources().getDisplayMetrics().density;
        int padding = Math.round(8 * density);
        LinearLayout content = new LinearLayout(themed);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(padding * 3, padding, padding * 3, padding);
        editor = new EditText(themed);
        editor.setId(android.R.id.text1);
        editor.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        editor.setSingleLine(true);
        editor.setTextSize(16);
        editor.setMinHeight(Math.round(48 * density));
        editor.setPadding(padding, padding, padding, padding);
        editor.setHint(hint);
        editor.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        content.addView(editor, new LinearLayout.LayoutParams(-1, -2));
        dialog = builder.setTitle(title).setView(content)
                .setPositiveButton(android.R.string.ok, null)
                .setNegativeButton(android.R.string.cancel, null).create();
        Runnable confirm = () -> {
            String name = editor.getText().toString();
            if (!name.isEmpty() && submit.submit(name)) dialog.dismiss();
        };
        dialog.setOnShowListener(ignored -> {
            Button positive = dialog.getButton(AlertDialog.BUTTON_POSITIVE);
            positive.setEnabled(editor.length() > 0);
            positive.setOnClickListener(view -> confirm.run());
            editor.requestFocus();
            editor.post(() -> ((InputMethodManager) themed.getSystemService(Context.INPUT_METHOD_SERVICE))
                    .showSoftInput(editor, InputMethodManager.SHOW_IMPLICIT));
        });
        editor.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                Button positive = dialog.getButton(AlertDialog.BUTTON_POSITIVE);
                if (positive != null) positive.setEnabled(s.length() > 0);
            }
            @Override public void afterTextChanged(Editable text) { }
        });
        editor.setOnEditorActionListener((view, action, event) -> {
            if (action == EditorInfo.IME_ACTION_DONE || (event != null
                    && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                    && event.getAction() == KeyEvent.ACTION_UP && event.hasNoModifiers())) {
                confirm.run(); return true;
            }
            return false;
        });
        dialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_PAN);
    }
}
