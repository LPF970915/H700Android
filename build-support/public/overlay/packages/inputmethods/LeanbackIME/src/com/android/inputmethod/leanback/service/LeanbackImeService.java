/*
 * Copyright (C) 2019 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License
 */

package com.android.inputmethod.leanback.service;

import android.content.Intent;
import android.inputmethodservice.InputMethodService;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.inputmethod.CompletionInfo;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.util.Log;

import com.android.inputmethod.leanback.LeanbackKeyboardContainer;
import com.android.inputmethod.leanback.LeanbackKeyboardController;
import com.android.inputmethod.leanback.LeanbackKeyboardView;
import com.android.inputmethod.leanback.LeanbackLocales;
import com.android.inputmethod.leanback.LeanbackSuggestionsFactory;
import com.android.inputmethod.leanback.LeanbackUtils;
import com.android.inputmethod.leanback.PinyinDictionary;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * This is a simplified version of GridIme
 */
public class LeanbackImeService extends InputMethodService {

    private static final String TAG = "LbImeService";
    private static final boolean DEBUG = false;

    // use dpad events, with lock axis
    static final int MODE_TRACKPAD_NAVIGATION = 0;
    // track motion directly.
    static final int MODE_FREE_MOVEMENT = 1;

    public static final int MAX_SUGGESTIONS = 10;

    private static final int MSG_SUGGESTIONS_CLEAR = 123;
    private static final int SUGGESTIONS_CLEAR_DELAY = 1000;

    public static final String IME_OPEN = "com.android.inputmethod.leanback.action.IME_OPEN";
    public static final String IME_CLOSE = "com.android.inputmethod.leanback.action.IME_CLOSE";

    private LeanbackKeyboardController.InputListener mInputListener
            = new LeanbackKeyboardController.InputListener() {
        @Override
        public void onEntry(int type, int keyCode, CharSequence result) {
            handleTextEntry(type, keyCode, result);
        }
    };

    private View mInputView;
    private LeanbackKeyboardController mKeyboardController;
    private LeanbackSuggestionsFactory mSuggestionsFactory;
    private boolean mOpeningWithConfirm;
    private boolean mBackConsumed;

    private static final int PAGE_SIZE = 5;
    private static final String SWITCH_TO_ENGLISH = "中 → EN";
    private static final String SWITCH_TO_CHINESE = "EN → 中";
    private static final String PREVIOUS_PAGE = "‹";
    private static final String NEXT_PAGE = "›";
    private final StringBuilder mSpelling = new StringBuilder();
    private PinyinDictionary mPinyinDictionary;
    private boolean mPinyinEditor;
    private boolean mChinese;
    private List<PinyinDictionary.Candidate> mCandidates = Collections.emptyList();
    private int mPage;

    private boolean isRgspConfirm(int keyCode, KeyEvent event) {
        if (!"rgsp".equals(android.os.Build.DEVICE)) {
            return false;
        }
        // Keep the virtual Enter event used to start editing.
        if (keyCode == KeyEvent.KEYCODE_ENTER && event.getDeviceId() == -1) {
            return true;
        }
        if (keyCode != KeyEvent.KEYCODE_BUTTON_A || event.getScanCode() != 304) {
            return false;
        }
        InputDevice device = event.getDevice();
        return device != null && "ANBERNIC-keys".equals(device.getName());
    }

    // IME will auto insert space after clicking on the candidates if next
    // character is alphabet
    private boolean mEnterSpaceBeforeCommitting;

    private boolean mShouldClearSuggestions = true;
    private final Handler mHandler = new Handler() {
        @Override
        public void handleMessage(Message msg) {
            if (msg.what == MSG_SUGGESTIONS_CLEAR) {
                if (mShouldClearSuggestions) {
                    mSuggestionsFactory.clearSuggestions();
                    updateCandidateStrip();
                    mShouldClearSuggestions = false;
                }
            }
        }
    };

    public LeanbackImeService() {
        if (!enableHardwareAcceleration()) {
            Log.w(TAG, "Could not enable hardware acceleration");
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        mChinese = getSharedPreferences("language", MODE_PRIVATE).getBoolean("chinese",
                "zh".equals(Locale.getDefault().getLanguage()));
        if (!"rgsp".equals(android.os.Build.DEVICE)) return;
        new Thread(() -> {
            try (FileInputStream source = new FileInputStream("/system/etc/rgsp/roc-pinyin.tsv.gz")) {
                PinyinDictionary dictionary = PinyinDictionary.load(source);
                mHandler.post(() -> {
                    mPinyinDictionary = dictionary;
                    if (isInputViewShown()) updateCandidateStrip();
                });
            } catch (IOException error) {
                Log.e(TAG, "Could not load offline Pinyin dictionary", error);
            }
        }, "roc-pinyin-load").start();
    }

    private void clearSuggestionsDelayed() {
        // if suggestions amend, we should keep clearing them
        if (!mSuggestionsFactory.shouldSuggestionsAmend()) {
            mHandler.removeMessages(MSG_SUGGESTIONS_CLEAR);
            mShouldClearSuggestions = true;
            mHandler.sendEmptyMessageDelayed(MSG_SUGGESTIONS_CLEAR, SUGGESTIONS_CLEAR_DELAY);
        }
    }

    @Override
    public void onInitializeInterface() {
        mKeyboardController = new LeanbackKeyboardController(this, mInputListener);
        mEnterSpaceBeforeCommitting = false;
        mSuggestionsFactory = new LeanbackSuggestionsFactory(this, MAX_SUGGESTIONS);
    }

    @Override
    public View onCreateInputView() {
        mInputView = mKeyboardController.getView();
        mInputView.requestFocus();
        return mInputView;
    }

    /**
     * {@inheritDoc} This function gets called whenever we start the input
     * window
     */
    @Override
    public void onStartInputView(EditorInfo info, boolean restarting) {
        super.onStartInputView(info, restarting);
        mKeyboardController.onStartInputView();
        sendBroadcast(new Intent(IME_OPEN));

        if (mKeyboardController.areSuggestionsEnabled()) {
            mSuggestionsFactory.createSuggestions();
            updateCandidateStrip();

            // RGSP must not rewrite the editor merely because the keyboard
            // opens. Text before/after the cursor excludes selected text, so
            // this legacy repost loses that selection and changes the cursor.
            // Existing suggestions are already refreshed above; real typing
            // continues to request completions normally.
            InputConnection ic = getCurrentInputConnection();
            if (ic != null && !"rgsp".equals(android.os.Build.DEVICE)) {
                String c = getEditorText(ic);
                ic.deleteSurroundingText(getCharLengthBeforeCursor(ic),
                        getCharLengthAfterCursor(ic));
                ic.commitText(c, 1);
            }
        }
    }


    @Override
    public void onFinishInputView(boolean finishingInput) {
        super.onFinishInputView(finishingInput);
        sendBroadcast(new Intent(IME_CLOSE));
        clearPinyin();
        mSuggestionsFactory.clearSuggestions();
    }

    /**
     * {@inheritDoc} This function doesn't get called when we dismiss the
     * keyboard, and reopen it on the same input field
     */
    @Override
    public void onStartInput(EditorInfo attribute, boolean restarting) {
        super.onStartInput(attribute, restarting);
        mOpeningWithConfirm = false;
        mBackConsumed = false;
        mEnterSpaceBeforeCommitting = false;
        clearPinyin();
        mPinyinEditor = LeanbackKeyboardContainer.supportsPinyin(attribute);
        mSuggestionsFactory.onStartInput(attribute);
        mKeyboardController.onStartInput(attribute);
    }

    /**
     * {@inheritDoc} Always return true to show GridIme when editText calls
     * requestFocus
     */
    @Override
    public boolean onShowInputRequested(int flags, boolean configChange) {
        return true;
    }

    /**
     * {@inheritDoc} Always enable soft keyboard. If we return the super method,
     * the IME will not be shown if there is a hardware keyboard connected
     */
    @Override
    public boolean onEvaluateInputViewShown() {
        return true;
    }

    @Override
    public boolean onEvaluateFullscreenMode() {
        // Superclass always returns true in landscape mode.
        // Assume we're on TV with lots of display area.
        return false;
    }

    @Override
    public boolean onKeyUp(int keyCode, KeyEvent event) {
        if (mBackConsumed && keyCode == KeyEvent.KEYCODE_BUTTON_B) {
            mBackConsumed = false;
            if (!event.isCanceled()) {
                if (mSpelling.length() > 0) {
                    clearPinyin();
                    updateCandidateStrip();
                } else {
                    requestHideSelf(0);
                }
            }
            return true;
        }
        if (isRgspConfirm(keyCode, event)) {
            if (mOpeningWithConfirm) {
                mOpeningWithConfirm = false;
                return true;
            }
            if (event.isCanceled()) {
                return true;
            }
            keyCode = KeyEvent.KEYCODE_DPAD_CENTER;
        }
        if (isInputViewShown()
                && mKeyboardController.onKeyUp(keyCode, event)) {
            return true;
        }
        return super.onKeyUp(keyCode, event);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (isInputViewShown() && keyCode == KeyEvent.KEYCODE_BUTTON_B) {
            mBackConsumed = true;
            return true;
        }
        if (isRgspConfirm(keyCode, event)) {
            if (!isInputViewShown() && getCurrentInputConnection() != null
                    && getCurrentInputEditorInfo() != null
                    && getCurrentInputEditorInfo().inputType != EditorInfo.TYPE_NULL) {
                mOpeningWithConfirm = true;
                requestShowSelf(0);
                return true;
            }
            if (mOpeningWithConfirm) {
                return true;
            }
            if (isInputViewShown()) {
                keyCode = KeyEvent.KEYCODE_DPAD_CENTER;
            }
        }
        if (isInputViewShown()
                && mKeyboardController.onKeyDown(keyCode, event)) {
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public boolean onGenericMotionEvent(MotionEvent event) {
        if (isInputViewShown() && (event.getSource() & InputDevice.SOURCE_TOUCH_NAVIGATION)
                == InputDevice.SOURCE_TOUCH_NAVIGATION) {
            if (mKeyboardController.onGenericMotionEvent(event)) {
                return true;
            }
        }
        return super.onGenericMotionEvent(event);
    }

    @Override
    public void onDisplayCompletions(CompletionInfo[] completions) {
        if (mKeyboardController.areSuggestionsEnabled()) {
            mShouldClearSuggestions = false;
            mHandler.removeMessages(MSG_SUGGESTIONS_CLEAR);
            mSuggestionsFactory.onDisplayCompletions(completions);
            updateCandidateStrip();
        }
    }

    private String getEditorText(InputConnection ic) {
        StringBuilder editorText = new StringBuilder();
        CharSequence textBeforeCursor = ic.getTextBeforeCursor(1000, 0);
        CharSequence textAfterCursor = ic.getTextAfterCursor(1000, 0);
        if (textBeforeCursor != null) {
            editorText.append(textBeforeCursor);
        }
        if (textAfterCursor != null) {
            editorText.append(textAfterCursor);
        }
        return editorText.toString();
    }

    private int getAmpersandLocation(InputConnection ic) {
        String editorText = getEditorText(ic);
        int indexOf = editorText.indexOf('@');
        if (indexOf < 0) {
            indexOf = editorText.length();
        }

        return indexOf;
    }

    private int getCharLengthBeforeCursor(InputConnection ic) {
        final CharSequence textLeft = ic.getTextBeforeCursor(1000, 0);
        return textLeft != null ? textLeft.length() : 0;
    }

    private int getCharLengthAfterCursor(InputConnection ic ) {
        final CharSequence textRight = ic.getTextAfterCursor(1000, 0);
        return textRight != null ? textRight.length() : 0;
    }

    private String spellingLabel() {
        return "拼音 " + mSpelling;
    }

    private void clearPinyin() {
        mSpelling.setLength(0);
        mCandidates = Collections.emptyList();
        mPage = 0;
    }

    private void refreshPinyin() {
        mCandidates = mPinyinDictionary.candidates(mSpelling.toString());
        mPage = 0;
        updateCandidateStrip();
    }

    private void updateCandidateStrip() {
        if (!mKeyboardController.areSuggestionsEnabled()) return;
        ArrayList<String> labels = new ArrayList<>();
        if (mPinyinEditor && mPinyinDictionary != null) {
            labels.add(mChinese ? SWITCH_TO_ENGLISH : SWITCH_TO_CHINESE);
            if (mSpelling.length() > 0) {
                if (mPage > 0) labels.add(PREVIOUS_PAGE);
                int end = Math.min(mCandidates.size(), (mPage + 1) * PAGE_SIZE);
                for (int i = mPage * PAGE_SIZE; i < end; i++) labels.add(mCandidates.get(i).text);
                if (end < mCandidates.size()) labels.add(NEXT_PAGE);
                labels.add(spellingLabel());
            }
        }
        if (mSpelling.length() == 0) labels.addAll(mSuggestionsFactory.getSuggestions());
        mKeyboardController.updateSuggestions(labels);
    }

    private void commitPinyin(InputConnection editor, String text, int letters) {
        editor.commitText(text, 1);
        mSpelling.delete(0, letters);
        refreshPinyin();
    }

    private void commitDefaultPinyin(InputConnection editor) {
        int letters = mSpelling.length();
        if (letters == 0) return;
        String text = mSpelling.toString();
        if (!mCandidates.isEmpty() && mCandidates.get(0).letters == letters) {
            text = mCandidates.get(0).text;
        }
        commitPinyin(editor, text, letters);
    }

    private boolean handlePinyin(InputConnection editor, int type, CharSequence value) {
        if (!mPinyinEditor || mPinyinDictionary == null) return false;
        String label = value == null ? "" : value.toString();
        if (type == LeanbackKeyboardController.InputListener.ENTRY_TYPE_SUGGESTION
                && (SWITCH_TO_CHINESE.equals(label) || SWITCH_TO_ENGLISH.equals(label))) {
            commitDefaultPinyin(editor);
            mChinese = SWITCH_TO_CHINESE.equals(label);
            getSharedPreferences("language", MODE_PRIVATE).edit().putBoolean("chinese", mChinese).apply();
            updateCandidateStrip();
            return true;
        }
        if (!mChinese) return false;
        int letters = mSpelling.length();
        switch (type) {
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_STRING:
                if (label.length() == 1) {
                    char letter = Character.toLowerCase(label.charAt(0));
                    if (letter >= 'a' && letter <= 'z') {
                        if (letters == PinyinDictionary.MAX_INPUT) commitDefaultPinyin(editor);
                        mSpelling.append(letter);
                        refreshPinyin();
                        return true;
                    }
                }
                commitDefaultPinyin(editor);
                return letters > 0 && " ".equals(label);
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_BACKSPACE:
                if (letters == 0) return false;
                mSpelling.setLength(letters - 1);
                refreshPinyin();
                return true;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_SUGGESTION:
                if (letters == 0) return false;
                if (PREVIOUS_PAGE.equals(label) && mPage > 0) {
                    mPage--;
                    updateCandidateStrip();
                } else if (NEXT_PAGE.equals(label) && (mPage + 1) * PAGE_SIZE < mCandidates.size()) {
                    mPage++;
                    updateCandidateStrip();
                } else if (spellingLabel().equals(label)) {
                    commitPinyin(editor, mSpelling.toString(), letters);
                } else {
                    for (PinyinDictionary.Candidate candidate : mCandidates) {
                        if (candidate.text.equals(label)) {
                            commitPinyin(editor, candidate.text, candidate.letters);
                            break;
                        }
                    }
                }
                return true;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_LEFT:
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_RIGHT:
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_ACTION:
                commitDefaultPinyin(editor);
                return false;
            default:
                return false;
        }
    }

    private void handleTextEntry(int type, int keyCode, CharSequence c) {
        InputConnection ic = getCurrentInputConnection();
        boolean updateSuggestions = true;

        if (ic == null || handlePinyin(ic, type, c)) {
            return;
        }

        switch (type) {
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_BACKSPACE:
                clearSuggestionsDelayed();
                ic.deleteSurroundingText(1, 0);
                mEnterSpaceBeforeCommitting = false;
                break;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_LEFT:
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_RIGHT:
                CharSequence textBeforeCursor = ic.getTextBeforeCursor(1000, 0);
                int newCursorPosition = textBeforeCursor == null ? 0 : textBeforeCursor.length();

                if (type == LeanbackKeyboardController.InputListener.ENTRY_TYPE_LEFT) {
                    if (newCursorPosition > 0) {
                        newCursorPosition--;
                    }
                } else {
                    CharSequence textAfterCursor = ic.getTextAfterCursor(1000, 0);
                    if (textAfterCursor != null && textAfterCursor.length() > 0) {
                        newCursorPosition++;
                    }
                }

                ic.setSelection(newCursorPosition, newCursorPosition);
                break;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_STRING:
                clearSuggestionsDelayed();
                if (mEnterSpaceBeforeCommitting
                        && mKeyboardController.enableAutoEnterSpace()) {
                    if (LeanbackUtils.isAlphabet(keyCode)) {
                        ic.commitText(" ", 1);
                    }
                    mEnterSpaceBeforeCommitting = false;
                }
                ic.commitText(c, 1);
                if (keyCode == LeanbackKeyboardView.ASCII_PERIOD) {
                    mEnterSpaceBeforeCommitting = true;
                }
                break;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_SUGGESTION:
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_VOICE:
                clearSuggestionsDelayed();
                if (!mSuggestionsFactory.shouldSuggestionsAmend()) {
                    ic.deleteSurroundingText(getCharLengthBeforeCursor(ic),
                            getCharLengthAfterCursor(ic));
                } else {
                    int location = getAmpersandLocation(ic);
                    ic.setSelection(location, location);
                    ic.deleteSurroundingText(0, getCharLengthAfterCursor(ic));
                }
                ic.commitText(c, 1);
                mEnterSpaceBeforeCommitting = true;
                // go straight into action (skip updating suggestions)
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_ACTION:
                sendDefaultEditorAction(false);
                updateSuggestions = false;
                break;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_DISMISS:
                ic.performEditorAction(EditorInfo.IME_ACTION_NONE);
                updateSuggestions = false;
                break;
            case LeanbackKeyboardController.InputListener.ENTRY_TYPE_VOICE_DISMISS:
                ic.performEditorAction(EditorInfo.IME_ACTION_GO);
                updateSuggestions = false;
                break;
        }

        if (mKeyboardController.areSuggestionsEnabled() && updateSuggestions) {
            updateCandidateStrip();
        }
    }

    public void onHideIme() {
        requestHideSelf(0);
    }
}
