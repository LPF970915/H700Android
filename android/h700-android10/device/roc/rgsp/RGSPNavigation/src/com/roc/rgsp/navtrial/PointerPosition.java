package com.roc.rgsp.navtrial;

/** Display-pixel coordinates; preserves relative position across geometry changes. */
final class PointerPosition {
    int width, height;
    float x, y;

    void resize(int width, int height) {
        if (width < 1 || height < 1) return;
        x = this.width > 1 ? x / (this.width - 1) * (width - 1) : (width - 1) / 2f;
        y = this.height > 1 ? y / (this.height - 1) * (height - 1) : (height - 1) / 2f;
        this.width = width;
        this.height = height;
        clamp();
    }

    void move(float dx, float dy) {
        x += dx;
        y += dy;
        clamp();
    }

    private void clamp() {
        x = Math.max(0, Math.min(Math.max(0, width - 1), x));
        y = Math.max(0, Math.min(Math.max(0, height - 1), y));
    }
}
