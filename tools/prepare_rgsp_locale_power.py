"""Prepare native locale selection and power-menu focus with pinned inputs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = 'packages/apps/Settings/src/com/android/settings/localepicker/LocaleDragAndDropAdapter.java'
POWER = 'frameworks/base/packages/SystemUI/src/com/android/systemui/globalactions/GlobalActionsDialog.java'
LOCALE_OLD = '        dragCell.setTag(feedItem);'
LOCALE_NEW = '''        dragCell.setTag(feedItem);
        if ("rgsp".equals(android.os.Build.DEVICE)) {
            // A controller cannot drag rows. Confirm promotes the chosen locale.
            dragCell.setFocusable(true);
            dragCell.setOnClickListener(v -> {
                final int position = holder.getAdapterPosition();
                if (position < 0 || position >= mFeedItemList.size()) return;
                if (mRemoveMode) {
                    dragCell.getCheckbox().performClick();
                } else if (position > 0) {
                    onItemMove(position, 0);
                    doTheUpdate();
                }
            });
        }'''
POWER_OLD = '''            view.setOnLongClickListener(v -> onLongClickItem(position));
            return view;'''
POWER_DIALOG_OLD = '        private ResetOrientationData mResetOrientationData;'
POWER_DIALOG_NEW = '''        private ResetOrientationData mResetOrientationData;
        private int mRgspHatDirection;

        private void collectRgspPowerActions(View view, java.util.List<View> actions) {
            if (view.getVisibility() != View.VISIBLE || !view.isEnabled()) return;
            if (Boolean.TRUE.equals(view.getTag(com.android.systemui.R.id.global_actions_view))) {
                actions.add(view);
                return;
            }
            if (view instanceof ViewGroup) {
                ViewGroup group = (ViewGroup) view;
                for (int i = 0; i < group.getChildCount(); i++) {
                    collectRgspPowerActions(group.getChildAt(i), actions);
                }
            }
        }

        private void moveRgspPowerFocus(int delta) {
            java.util.ArrayList<View> actions = new java.util.ArrayList<>();
            collectRgspPowerActions(mGlobalActionsLayout, actions);
            if (actions.isEmpty()) return;
            int index = actions.indexOf(getWindow().getDecorView().findFocus());
            index = index < 0 ? 0 : Math.max(0, Math.min(actions.size() - 1, index + delta));
            actions.get(index).requestFocus();
        }

        @Override
        public boolean dispatchKeyEvent(android.view.KeyEvent event) {
            int key = event.getKeyCode();
            if ("rgsp".equals(android.os.Build.DEVICE)
                    && key >= android.view.KeyEvent.KEYCODE_DPAD_UP
                    && key <= android.view.KeyEvent.KEYCODE_DPAD_RIGHT) {
                if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
                    moveRgspPowerFocus(key == android.view.KeyEvent.KEYCODE_DPAD_UP
                            || key == android.view.KeyEvent.KEYCODE_DPAD_LEFT ? -1 : 1);
                }
                return true;
            }
            return super.dispatchKeyEvent(event);
        }

        @Override
        public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
            if ("rgsp".equals(android.os.Build.DEVICE)
                    && event.isFromSource(android.view.InputDevice.SOURCE_JOYSTICK)
                    && event.getDevice() != null
                    && "ANBERNIC-keys".equals(event.getDevice().getName())) {
                if (event.getActionMasked() == android.view.MotionEvent.ACTION_CANCEL) {
                    mRgspHatDirection = 0;
                    return true;
                }
                if (event.getActionMasked() == android.view.MotionEvent.ACTION_MOVE) {
                    float x = event.getAxisValue(android.view.MotionEvent.AXIS_HAT_X);
                    float y = event.getAxisValue(android.view.MotionEvent.AXIS_HAT_Y);
                    int direction = x < -0.5f || y < -0.5f ? -1
                            : x > 0.5f || y > 0.5f ? 1 : 0;
                    if (direction != mRgspHatDirection && direction != 0) {
                        moveRgspPowerFocus(direction);
                    }
                    mRgspHatDirection = direction;
                    return true;
                }
            }
            return super.dispatchGenericMotionEvent(event);
        }'''
POWER_START_OLD = '''            mGlobalActionsLayout.updateList();

            if (mBackgroundDrawable instanceof ScrimDrawable) {'''
POWER_START_NEW = '''            mGlobalActionsLayout.updateList();
            if ("rgsp".equals(android.os.Build.DEVICE)) {
                mRgspHatDirection = 0;
                mGlobalActionsLayout.post(() -> moveRgspPowerFocus(1));
            }

            if (mBackgroundDrawable instanceof ScrimDrawable) {'''
POWER_NEW = '''            view.setOnLongClickListener(v -> onLongClickItem(position));
            if ("rgsp".equals(android.os.Build.DEVICE)) {
                // Native focus also works before the accessibility service starts.
                view.setFocusable(true);
                view.setFocusableInTouchMode(true);
                final android.graphics.drawable.Drawable original = view.getForeground();
                final android.graphics.drawable.GradientDrawable focus =
                        new android.graphics.drawable.GradientDrawable();
                final float density = mContext.getResources().getDisplayMetrics().density;
                focus.setColor(0x3333b5e5);
                focus.setStroke(Math.max(2, Math.round(3 * density)), 0xff33b5e5);
                focus.setCornerRadius(8 * density);
                view.setOnFocusChangeListener((v, focused) ->
                        v.setForeground(focused ? focus : original));
            }
            return view;'''
POWER_PREVIOUS = POWER_NEW
POWER_NEW = POWER_NEW.replace('                view.setFocusable(true);',
    '                view.setTag(com.android.systemui.R.id.global_actions_view, Boolean.TRUE);\n'
    '                view.setFocusable(true);')
PATCHES = {
    LOCALE: ('1f0f9ded149469dee6eed9218461cee015c16b0c05c7acc3b2298f71e1f6220c', LOCALE_OLD, LOCALE_NEW),
    POWER: ('95cdc68b91050cd1338a598698ac73be0a6965fcb716a0fe658fa10019a93b92', POWER_OLD, POWER_NEW),
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    record_path = args.source / 'out/rgsp-locale-power-inputs.json'
    previous = json.loads(record_path.read_text()) if record_path.exists() else {}
    planned = []
    for rel, (before, old, new) in PATCHES.items():
        path = args.source / rel
        base = path.read_text()
        edits = [(old, new)]
        if rel == POWER:
            base = base.replace(POWER_PREVIOUS, POWER_OLD, 1)
            edits.extend([(POWER_DIALOG_OLD, POWER_DIALOG_NEW), (POWER_START_OLD, POWER_START_NEW)])
        for original, replacement in reversed(edits):
            base = base.replace(replacement, original, 1)
        if digest(base.encode()) != before or base.count(old) != 1:
            raise SystemExit('Unrecognized native edits, preserved: ' + rel)
        for original, replacement in edits:
            if base.count(original) != 1:
                raise SystemExit('Ambiguous native anchor: ' + rel)
            base = base.replace(original, replacement, 1)
        planned.append((path, base.encode()))
    for name, before in {
        'BoardConfig.mk': '47d322403cc3c71f9167424fb444cc22b1e72028c360fc61002a157b83aadb7f',
        'h700_rgsp.mk': 'acd0f0fc734d8977be2336a8ebb333596611ace043f0da6aefb2a4aa182b6b5d',
        'rgsp-firstboot.sh': 'd65c05c226aed584ae31596e863cfefcdebb71da093fa238a7a9ff8a32f532d7',
    }.items():
        rel = Path('device/roc/rgsp') / name
        data = (ROOT / 'android/h700-android10' / rel).read_bytes().replace(b'\r\n', b'\n')
        path = args.source / rel
        if digest(path.read_bytes()) not in (before, digest(data), previous.get(rel.as_posix())):
            raise SystemExit('Unrecognized product edits, preserved: ' + name)
        planned.append((path, data))
    rel = Path('device/roc/rgsp/system.prop')
    path = args.source / rel
    data = (ROOT / 'android/h700-android10' / rel).read_bytes().replace(b'\r\n', b'\n')
    if path.exists() and path.read_bytes() != data:
        raise SystemExit('Unrecognized system.prop, preserved')
    planned.append((path, data))
    for path, data in planned:
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
    record = {str(path.relative_to(args.source)): digest(data) for path, data in planned}
    record_path.write_text(json.dumps(record, indent=2)+'\n')
    print('RGSP_LOCALE_POWER_FACTORY_INPUTS_PREPARED')

if __name__ == '__main__':
    main()
