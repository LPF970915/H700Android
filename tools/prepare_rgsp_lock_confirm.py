#!/usr/bin/env python3
"""Apply the RGSP physical-A swipe-keyguard fix to the pinned Android 10 UI."""
import argparse
import hashlib
from pathlib import Path

REL = 'frameworks/base/packages/SystemUI/src/com/android/systemui/statusbar/phone/StatusBarWindowView.java'
BEFORE = '7c670751033f065a321472937949e2cfad5ca01377f4bd1b8ffbc9d85bcddea1'
ANCHOR = '''    public boolean dispatchKeyEvent(KeyEvent event) {
        if (mService.interceptMediaKey(event)) {'''
REPLACEMENT = '''    public boolean dispatchKeyEvent(KeyEvent event) {
        // RGSP has no touchscreen. Physical A is ENTER for Settings/LeanbackIME,
        // but the swipe keyguard consumes ENTER before KCM fallback can run.
        // Handle only that controller on the keyguard, before child dispatch.
        // Keep credential entry with the bouncer and retain normal authentication.
        if ("rgsp".equals(android.os.Build.DEVICE)
                && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                && event.getScanCode() == 304
                && event.getDevice() != null
                && "ANBERNIC-keys".equals(event.getDevice().getName())
                && mService.isKeyguardShowing() && !mService.isBouncerShowing()) {
            if (event.getAction() == KeyEvent.ACTION_UP && !event.isCanceled()) {
                mService.onSpacePressed();
            }
            return true;
        }
        if (mService.interceptMediaKey(event)) {'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    path = args.source / REL
    raw = path.read_bytes()
    source = raw.decode('utf-8')
    if REPLACEMENT in source:
        original = source.replace(REPLACEMENT, ANCHOR, 1).encode('utf-8')
        if hashlib.sha256(original).hexdigest() != BEFORE:
            raise SystemExit('Patched SystemUI differs from the pinned source')
        print('ALREADY_APPLIED')
        return
    if hashlib.sha256(raw).hexdigest() != BEFORE or source.count(ANCHOR) != 1:
        raise SystemExit('Unexpected SystemUI source; refusing to overwrite it')
    path.write_text(source.replace(ANCHOR, REPLACEMENT, 1), encoding='utf-8')
    print('APPLIED', hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
