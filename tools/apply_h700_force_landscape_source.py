"""Apply the reviewed source equivalent of the pinned ActivityRecord DEX delta."""
from pathlib import Path
import argparse
import hashlib
import json

RELATIVE = Path('frameworks/base/services/core/java/com/android/server/wm/ActivityRecord.java')
BASE_SHA = 'c3a246f9d23cbc7bfa35e2fdf89aa724f3667ac09f17a61bf09ed87a6cdfea1d'
HELPER = '''    // H700: keep the primary display fully resizable while the system tile is on.
    // Existing app orientation and aspect-ratio behavior resumes when fixed rotation is off.
    private boolean h700ForceLandscape() {
        if (!"rgsp".equals(SystemProperties.get("ro.product.device"))) return false;
        final ActivityDisplay display = getDisplay();
        return display != null && display.mDisplayId == DEFAULT_DISPLAY
                && display.mDisplayContent != null
                && display.mDisplayContent.getDisplayRotation().isFixedToUserRotation();
    }

'''

def patch_java(text):
    if 'h700ForceLandscape' in text:
        raise ValueError('Source already has the H700 rotation patch')
    changes = {
        '    int getRequestedConfigurationOrientation() {\n':
            HELPER + '    int getRequestedConfigurationOrientation() {\n'
            '        if (h700ForceLandscape()) return ORIENTATION_LANDSCAPE;\n',
        '    boolean shouldUseSizeCompatMode() {\n':
            '    boolean shouldUseSizeCompatMode() {\n'
            '        if (h700ForceLandscape()) return false;\n',
        '    private void computeBounds(Rect outBounds, Rect containingAppBounds) {\n        outBounds.setEmpty();\n':
            '    private void computeBounds(Rect outBounds, Rect containingAppBounds) {\n'
            '        outBounds.setEmpty();\n'
            '        if (h700ForceLandscape()) return;\n',
        '    void resolveOverrideConfiguration(Configuration newParentConfiguration) {\n':
            '    void resolveOverrideConfiguration(Configuration newParentConfiguration) {\n'
            '        if (h700ForceLandscape()) mCompatDisplayInsets = null;\n',
    }
    for old, new in changes.items():
        if text.count(old) != 1: raise ValueError('Unexpected source structure: ' + old.splitlines()[0])
        text = text.replace(old, new, 1)
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    target = source / RELATIVE
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(source):
        raise ValueError('Unexpected framework source path')
    before = target.read_bytes()
    if hashlib.sha256(before).hexdigest() != BASE_SHA:
        raise ValueError('Unrecognized ActivityRecord input; review instead of overwriting')
    after = patch_java(before.decode('utf-8')).encode('utf-8')
    if args.apply:
        if args.backup is None: raise ValueError('An explicit new backup directory is required')
        backup = args.backup.absolute()
        if backup.exists() or backup.resolve().is_relative_to(source): raise ValueError('Backup must be new and outside source')
        backup.mkdir(parents=True)
        (backup / 'ActivityRecord.java').write_bytes(before)
        target.write_bytes(after)
        assert target.read_bytes() == after
    print(json.dumps({'mode':'apply' if args.apply else 'plan', 'path':str(RELATIVE),
        'before_sha256':BASE_SHA,'after_sha256':hashlib.sha256(after).hexdigest()},indent=2))

if __name__ == '__main__': main()
