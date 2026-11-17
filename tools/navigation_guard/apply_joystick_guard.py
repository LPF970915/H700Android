"""Produce an isolated, SHA-bound ViewRootImpl candidate; never edit its source.

This is not a framework build or an installable patch. The unchanged original
SyntheticJoystickHandler remains the path for every application outside the
four explicit navigation packages. Run the candidate's tests before integration.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json

SOURCE_SHA256 = "0eadf38bc8ceb599dcf57eb2d6a8b9e818a19ecedca1143b3a361682c0e64639"
ALLOWLIST = ("com.overdevs.at4k", "com.android.settings", "com.android.documentsui", "com.android.systemui")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("source anchor missing or ambiguous: " + old[:100])
    return text.replace(old, new, 1)


def make_candidate(original):
    if sha(original) != SOURCE_SHA256:
        raise ValueError("source SHA mismatch; no candidate written")
    text = original.decode("utf-8")
    snippet = Path(__file__).with_name("RocJoystickGuard.java.inc").read_text(encoding="utf-8")
    package_checks = "\n                || ".join('"' + package + '".equals(packageName)' for package in ALLOWLIST)
    helper = '''    // ROC navigation scope is exact: games and other applications retain legacy input.
    private boolean isRocNavigationGuardEnabled() {
        final String packageName = mContext.getPackageName();
        return ''' + package_checks + ''';
    }

    // Shared lifecycle anchor; the standalone DPAD candidate can add its own guard here.
    private void onRocNavigationDisplayChanged() {
        if (mSyntheticInputStage != null) {
            ((SyntheticInputStage) mSyntheticInputStage).onRocDisplayStateChanged();
        }
    }

    // Private queue provenance distinguishes this guard from other FALLBACK events.
    private void enqueueRocJoystickEvent(KeyEvent event) {
        enqueueInputEvent(event, null, QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED, false);
    }

    private boolean rocShouldBlockJoystick(QueuedInputEvent q) {
        if ((q.mFlags & QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED) == 0) return false;
        if (!(q.mEvent instanceof KeyEvent) || !(mSyntheticInputStage instanceof SyntheticInputStage)) {
            return true;
        }
        return ((SyntheticInputStage) mSyntheticInputStage).mJoystick.mRocGuard
                .shouldBlockDelivery((KeyEvent) q.mEvent);
    }

    private void rocFinishJoystickEvent(QueuedInputEvent q) {
        if ((q.mFlags & QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED) != 0
                && q.mEvent instanceof KeyEvent && mSyntheticInputStage instanceof SyntheticInputStage) {
            ((SyntheticInputStage) mSyntheticInputStage).mJoystick.mRocGuard
                    .finishDelivery((KeyEvent) q.mEvent);
        }
    }

'''
    text = replace_once(text, "    private final DisplayListener mDisplayListener = new DisplayListener() {",
            helper + "    private final DisplayListener mDisplayListener = new DisplayListener() {")
    text = replace_once(text,
            "        public static final int FLAG_MODIFIED_FOR_COMPATIBILITY = 1 << 6;",
            "        public static final int FLAG_MODIFIED_FOR_COMPATIBILITY = 1 << 6;\n        private static final int FLAG_ROC_JOYSTICK_GUARDED = 1 << 9;")
    text = replace_once(text, "                    mAttachInfo.mDisplayState = newDisplayState;\n                    pokeDrawLockIfNeeded();",
            "                    mAttachInfo.mDisplayState = newDisplayState;\n                    onRocNavigationDisplayChanged();\n                    pokeDrawLockIfNeeded();")
    text = replace_once(text, "        public void onDisplayRemoved(int displayId) {\n        }",
            "        public void onDisplayRemoved(int displayId) {\n            if (mDisplay != null && mDisplay.getDisplayId() == displayId) {\n                onRocNavigationDisplayChanged();\n            }\n        }")
    text = replace_once(text, "        mAttachInfo.mDisplayState = mDisplay.getState();\n        // Internal state updated, now notify the view hierarchy.",
            "        mAttachInfo.mDisplayState = mDisplay.getState();\n        onRocNavigationDisplayChanged();\n        // Internal state updated, now notify the view hierarchy.")
    text = replace_once(text, "            mStopped = stopped;\n            final ThreadedRenderer renderer = mAttachInfo.mThreadedRenderer;",
            "            mStopped = stopped;\n            if (mStopped) onRocNavigationDisplayChanged();\n            final ThreadedRenderer renderer = mAttachInfo.mThreadedRenderer;")
    post_start = text.index("    final class ViewPostImeInputStage extends InputStage {")
    post_end = text.index("    final class SyntheticInputStage extends InputStage {", post_start)
    post_stage = text[post_start:post_end]
    post_stage = replace_once(post_stage,
            "        private int processKeyEvent(QueuedInputEvent q) {\n            final KeyEvent event = (KeyEvent)q.mEvent;",
            "        private int processKeyEvent(QueuedInputEvent q) {\n            final KeyEvent event = (KeyEvent)q.mEvent;\n            if (rocShouldBlockJoystick(q)) return FINISH_HANDLED;")
    text = text[:post_start] + post_stage + text[post_end:]
    text = replace_once(text, "    private void finishInputEvent(QueuedInputEvent q) {\n",
            "    private void finishInputEvent(QueuedInputEvent q) {\n        rocFinishJoystickEvent(q);\n")
    stage_anchor = """        @Override
        protected void onWindowFocusChanged(boolean hasWindowFocus) {
            if (!hasWindowFocus) {
                mJoystick.cancel();
            }
        }

        @Override
        protected void onDetachedFromWindow() {
            mJoystick.cancel();
        }
    }
"""
    stage_helper = """        void onRocDisplayStateChanged() {
            mJoystick.onRocDisplayStateChanged();
        }

"""
    text = replace_once(text, stage_anchor, stage_helper + stage_anchor)
    text = replace_once(text,
            "                    } else if ((source & InputDevice.SOURCE_CLASS_JOYSTICK) != 0) {\n                        mJoystick.cancel();",
            "                    } else if ((source & InputDevice.SOURCE_CLASS_JOYSTICK) != 0) {\n                        mJoystick.cancel(event);")
    start = text.index("    final class SyntheticJoystickHandler extends Handler {")
    end = text.index("    /**\n     * Creates dpad events from unhandled touch navigation movements.", start)
    legacy = text[start:end]
    changed = replace_once(legacy,
            "        private final JoystickAxesState mJoystickAxesState = new JoystickAxesState();",
            "        private final RocJoystickGuard mRocGuard = new RocJoystickGuard();\n\n        private final JoystickAxesState mJoystickAxesState = new JoystickAxesState();")
    changed = replace_once(changed, "        public void process(MotionEvent event) {\n",
            "        public void process(MotionEvent event) {\n            if (isRocNavigationGuardEnabled()) {\n                mRocGuard.process(event);\n                return;\n            }\n")
    changed = replace_once(changed, "        private void cancel() {\n",
            "        private void cancel() {\n            if (isRocNavigationGuardEnabled()) {\n                mRocGuard.cancel();\n                return;\n            }\n")
    changed = replace_once(changed, "        private void update(MotionEvent event) {\n",
            "        void onRocDisplayStateChanged() {\n            if (isRocNavigationGuardEnabled()) mRocGuard.cancel();\n        }\n\n        private void cancel(MotionEvent event) {\n            if (isRocNavigationGuardEnabled()) {\n                mRocGuard.cancel(event);\n            } else {\n                cancel();\n            }\n        }\n\n        private void update(MotionEvent event) {\n")
    # Guard insertion must not replace, truncate or rewrite legacy axis/repeat code.
    text = text[:start] + snippet.rstrip() + "\n\n" + changed + text[end:]
    result = text.encode("utf-8")
    return result, {"expected_source_sha256": SOURCE_SHA256, "result_sha256": sha(result),
            "guard_sha256": sha(snippet.encode("utf-8")), "scope_packages": list(ALLOWLIST),
            "original_source_untouched": True, "installable": False,
            "legacy_handler_preserved_except_scoped_routing": True,
            "display_forwarding": ["onDisplayChanged", "onDisplayRemoved", "onMovedToDisplay"],
            "window_stopped_forwarding": True,
            "prior_consumer_identity_cancel": True, "per_session_stop_boundary": True,
            "private_queue_provenance_flag": "FLAG_ROC_JOYSTICK_GUARDED=1<<9",
            "post_ime_delivery_gate": True, "finish_before_recycle_cleanup": True,
            "initial_repeat_ms": 400, "repeat_interval_ms": 160,
            "synthetic_stage_null_safe": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    original = args.source.read_bytes()
    result, manifest = make_candidate(original)
    if args.work.exists():
        raise SystemExit("work already exists; use a fresh isolated directory")
    if args.work.resolve() == args.source.parent.resolve():
        raise SystemExit("refusing source directory")
    args.work.mkdir(parents=True)
    (args.work / "ViewRootImpl.java").write_bytes(result)
    patch = "".join(difflib.unified_diff(original.decode().splitlines(True), result.decode().splitlines(True),
            fromfile="a/frameworks/base/core/java/android/view/ViewRootImpl.java",
            tofile="b/frameworks/base/core/java/android/view/ViewRootImpl.java"))
    (args.work / "ViewRootImpl.patch").write_text(patch, encoding="utf-8", newline="\n")
    manifest["patch_sha256"] = sha(patch.encode())
    (args.work / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
