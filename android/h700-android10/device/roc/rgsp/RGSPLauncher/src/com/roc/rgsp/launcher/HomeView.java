package com.roc.rgsp.launcher;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;

import java.util.ArrayList;
import java.util.List;

final class HomeView extends View {
    private static final int BG = Color.rgb(22, 27, 34);
    private static final int PANEL = Color.rgb(34, 42, 52);
    private static final int CARD = Color.rgb(48, 59, 72);
    private static final int ACCENT = Color.rgb(87, 190, 164);
    private static final int TEXT = Color.rgb(239, 243, 246);
    private static final int MUTED = Color.rgb(164, 177, 188);
    private static final int PAGE_SIZE = 8;

    private final MainActivity activity;
    private final List<MainActivity.AppEntry> apps;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rect = new RectF();
    private boolean menu;
    private int focus;
    private int page;
    private int menuFocus;
    private int menuScroll;

    HomeView(MainActivity activity, List<MainActivity.AppEntry> apps) {
        super(activity);
        this.activity = activity;
        this.apps = apps;
        setFocusable(true);
        setFocusableInTouchMode(true);
        requestFocus();
        paint.setTypeface(android.graphics.Typeface.create("sans", 0));
    }

    @Override protected void onDraw(Canvas c) {
        super.onDraw(c);
        c.drawColor(BG);
        int w = getWidth();
        int h = getHeight();
        paint.setColor(TEXT);
        paint.setTextSize(22);
        c.drawText("RGSP HOME", 24, 32, paint);
        paint.setColor(MUTED);
        paint.setTextSize(16);
        c.drawText("720 x 480", w - 98, 30, paint);
        drawCards(c, w);
        drawFooter(c, w, h);
        if (menu) drawMenu(c, w, h);
    }

    private void drawCards(Canvas c, int w) {
        int left = 24;
        int top = 62;
        int gap = 12;
        int cardW = (w - left * 2 - gap * 3) / 4;
        int cardH = 108;
        for (int i = 0; i < PAGE_SIZE; i++) {
            int col = i % 4;
            int row = i / 4;
            float x = left + col * (cardW + gap);
            float y = top + row * (cardH + gap);
            boolean selected = !menu && focus == i;
            rect.set(x, y, x + cardW, y + cardH);
            paint.setColor(selected ? ACCENT : CARD);
            c.drawRoundRect(rect, 8, 8, paint);
            if (page == 0 && i == 0) {
                drawLetter(c, "S", x + 14, y + 14);
                paint.setColor(TEXT);
                paint.setTextSize(16);
                c.drawText("Settings", x + 14, y + 84, paint);
            } else if (page == 0 && i == 1) {
                drawLetter(c, "F", x + 14, y + 14);
                paint.setColor(TEXT);
                paint.setTextSize(16);
                c.drawText("Files", x + 14, y + 84, paint);
            } else if (page == 0 && i == 2) {
                drawLetter(c, "A", x + 14, y + 14);
                paint.setColor(TEXT);
                paint.setTextSize(16);
                c.drawText("AT4K", x + 14, y + 84, paint);
            } else {
                int index = appIndex(i);
                if (index < 0 || index >= apps.size()) continue;
                MainActivity.AppEntry app = apps.get(index);
                drawIcon(c, app.icon, x + 14, y + 14, 48, 48);
                paint.setColor(TEXT);
                paint.setTextSize(16);
                c.drawText(trim(app.label, 16), x + 14, y + 84, paint);
            }
        }
    }

    private void drawFooter(Canvas c, int w, int h) {
        float top = h - 62;
        paint.setColor(PANEL);
        c.drawRect(0, top, w, h, paint);
        paint.setColor(MUTED);
        paint.setTextSize(15);
        c.drawText("A Open", 24, top + 38, paint);
        c.drawText("B Back", 120, top + 38, paint);
        c.drawText("MENU Options", 222, top + 38, paint);
        c.drawText("L/R Page", w - 115, top + 38, paint);
        paint.setColor(ACCENT);
        paint.setTextSize(14);
        c.drawText((page + 1) + "/" + Math.max(1, (apps.size() + PAGE_SIZE - 1) / PAGE_SIZE),
                w / 2f - 8, top + 38, paint);
    }

    private void drawMenu(Canvas c, int w, int h) {
        paint.setColor(Color.argb(215, 0, 0, 0));
        c.drawRect(0, 0, w, h, paint);
        int menuW = Math.min(390, w - 48);
        int menuH = Math.min(350, h - 92);
        float left = (w - menuW) / 2f;
        float top = 42;
        paint.setColor(PANEL);
        rect.set(left, top, left + menuW, top + menuH);
        c.drawRoundRect(rect, 8, 8, paint);
        paint.setColor(TEXT);
        paint.setTextSize(22);
        c.drawText("Options", left + 20, top + 34, paint);
        String[] choices = {"System settings", "All applications", "AT4K launcher", "Launcher3 recovery", "Power menu"};
        int rowH = 48;
        int first = menuScroll;
        for (int i = first; i < choices.length && i < first + 5; i++) {
            float y = top + 48 + (i - first) * rowH;
            boolean selected = i == menuFocus;
            paint.setColor(selected ? ACCENT : CARD);
            rect.set(left + 14, y, left + menuW - 14, y + rowH - 5);
            c.drawRoundRect(rect, 6, 6, paint);
            paint.setColor(TEXT);
            paint.setTextSize(18);
            c.drawText(choices[i], left + 28, y + 29, paint);
        }
        paint.setColor(MUTED);
        paint.setTextSize(13);
        c.drawText("UP/DOWN move   A select   B close", left + 20, top + menuH - 16, paint);
    }

    private void drawLetter(Canvas c, String letter, float x, float y) {
        paint.setColor(Color.rgb(72, 112, 142));
        rect.set(x, y, x + 48, y + 48);
        c.drawRoundRect(rect, 7, 7, paint);
        paint.setColor(Color.WHITE);
        paint.setTextSize(28);
        c.drawText(letter, x + 13, y + 34, paint);
    }

    private void drawIcon(Canvas c, Drawable icon, float x, float y, int size, int unused) {
        if (icon == null) { drawLetter(c, "?", x, y); return; }
        icon.setBounds((int) x, (int) y, (int) x + size, (int) y + size);
        icon.draw(c);
    }

    private String trim(String text, int max) {
        return text.length() <= max ? text : text.substring(0, max - 1) + "...";
    }

    @Override public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (menu) return menuKey(keyCode);
        int total = page == 0
                ? Math.max(3, Math.min(PAGE_SIZE, apps.size() + 3))
                : Math.min(PAGE_SIZE, Math.max(1, apps.size() - 5 - (page - 1) * PAGE_SIZE));
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_LEFT: focus = (focus + 3) % 4 + (focus / 4) * 4; break;
            case KeyEvent.KEYCODE_DPAD_RIGHT: focus = (focus + 1) % 4 + (focus / 4) * 4; break;
            case KeyEvent.KEYCODE_DPAD_UP: focus = Math.max(0, focus - 4); break;
            case KeyEvent.KEYCODE_DPAD_DOWN: focus = Math.min(total - 1, focus + 4); break;
            case KeyEvent.KEYCODE_PAGE_DOWN:
            case KeyEvent.KEYCODE_MEDIA_NEXT: page = Math.min(maxPage(), page + 1); focus = 0; break;
            case KeyEvent.KEYCODE_PAGE_UP:
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS: page = Math.max(0, page - 1); focus = 0; break;
            case KeyEvent.KEYCODE_MENU: menu = true; menuFocus = 0; menuScroll = 0; break;
            case KeyEvent.KEYCODE_BACK: return true;
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER: activate(); break;
            default: return super.onKeyDown(keyCode, event);
        }
        invalidate();
        return true;
    }

    private boolean menuKey(int keyCode) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_DPAD_UP: menuFocus = Math.max(0, menuFocus - 1); break;
            case KeyEvent.KEYCODE_DPAD_DOWN: menuFocus = Math.min(4, menuFocus + 1); break;
            case KeyEvent.KEYCODE_BACK: menu = false; break;
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER: activateMenu(); break;
            default: return true;
        }
        if (menuFocus < menuScroll) menuScroll = menuFocus;
        if (menuFocus >= menuScroll + 5) menuScroll = menuFocus - 4;
        invalidate();
        return true;
    }

    private void activate() {
        if (page == 0 && focus == 0) { activity.openSettings(); return; }
        if (page == 0 && focus == 1) { activity.openFiles(); return; }
        if (page == 0 && focus == 2) { activity.openAt4k(); return; }
        int index = appIndex(focus);
        if (index < apps.size()) {
            MainActivity.AppEntry app = apps.get(index);
            activity.launch(app.packageName, app.activityName);
        }
    }

    private void activateMenu() {
        switch (menuFocus) {
            case 0: activity.openSettings(); break;
            case 1: page = apps.size() > 5 ? 1 : 0; focus = 0; menu = false; break;
            case 2: activity.openAt4k(); break;
            case 3: activity.launch("com.android.launcher3", "com.android.launcher3.Launcher"); break;
            case 4: menu = false; break;
        }
        invalidate();
    }

    private int maxPage() {
        if (apps.size() <= 5) return 0;
        return 1 + (apps.size() - 5 + PAGE_SIZE - 1) / PAGE_SIZE - 1;
    }

    private int appIndex(int slot) {
        if (page == 0) return slot - 3;
        return 5 + (page - 1) * PAGE_SIZE + slot;
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() == MotionEvent.ACTION_UP) {
            float x = event.getX(), y = event.getY();
            if (y > getHeight() - 70) { menu = true; menuFocus = 0; menuScroll = 0; invalidate(); return true; }
            int col = (int) ((x - 24) / 173);
            int row = (int) ((y - 62) / 120);
            if (col >= 0 && col < 4 && row >= 0 && row < 2) { focus = row * 4 + col; activate(); invalidate(); }
            return true;
        }
        return true;
    }
}
