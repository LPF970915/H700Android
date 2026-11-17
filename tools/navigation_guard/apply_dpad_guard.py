"""Add the scoped physical-DPAD guard to the joystick-patched ViewRoot candidate.

No Android source or build output is edited in place. The caller supplies a new
output file. Anchors are exact and must occur once, including both lifecycle
hooks in the actual SyntheticInputStage and the private queue flag declaration.
"""
from pathlib import Path
import argparse
import hashlib
import json


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected one source anchor: ' + old[:100])
    return text.replace(old, new, 1)


def transform(source, snippet):
    if 'FLAG_ROC_DPAD_RELEASE' in source or 'class RocDpadKeyGuard' in source:
        raise ValueError('DPAD guard already present')
    marker = '    private boolean isRocNavigationGuardEnabled() {'
    source = once(source, marker, snippet + '\n' + marker)
    post_start = source.index('    final class ViewPostImeInputStage extends InputStage {')
    post_end = source.index('    final class SyntheticInputStage extends InputStage {', post_start)
    post = source[post_start:post_end]
    post = once(post,
        '        private int processKeyEvent(QueuedInputEvent q) {\n'
        '            final KeyEvent event = (KeyEvent)q.mEvent;',
        '        private int processKeyEvent(QueuedInputEvent q) {\n'
        '            if (rocShouldBlockDpad(q)) return FINISH_HANDLED;\n'
        '            final KeyEvent event = (KeyEvent)q.mEvent;')
    source = source[:post_start] + post + source[post_end:]
    # Other producers may prepend their own finish hook. Anchor only the actual
    # method declaration so both cleanups run before event/queue recycling.
    source = once(source,
        '    private void finishInputEvent(QueuedInputEvent q) {',
        '    private void finishInputEvent(QueuedInputEvent q) {\n'
        '        rocFinishDpadInputEvent(q);')
    source = once(source,
        '    private void onRocNavigationDisplayChanged() {',
        '    private void onRocNavigationDisplayChanged() {\n'
        '        rocCancelDpadForContext();')
    source = once(source,
        '        protected void onWindowFocusChanged(boolean hasWindowFocus) {\n'
        '            if (!hasWindowFocus) {\n'
        '                mJoystick.cancel();',
        '        protected void onWindowFocusChanged(boolean hasWindowFocus) {\n'
        '            if (!hasWindowFocus) {\n'
        '                rocCancelDpadForContext();\n'
        '                mJoystick.cancel();')
    source = once(source,
        '        protected void onDetachedFromWindow() {\n'
        '            mJoystick.cancel();',
        '        protected void onDetachedFromWindow() {\n'
        '            rocCancelDpadForContext();\n'
        '            mJoystick.cancel();')
    # FLAG_UNHANDLED is 1<<5 and FLAG_MODIFIED_FOR_COMPATIBILITY is 1<<6 in
    # the retained Android10 QueuedInputEvent; use the next unused private bit.
    source = once(source,
        '        public static final int FLAG_MODIFIED_FOR_COMPATIBILITY = 1 << 6;',
        '        public static final int FLAG_MODIFIED_FOR_COMPATIBILITY = 1 << 6;\n'
        '        public static final int FLAG_ROC_DPAD_RELEASE = 1 << 7;\n'
        '        public static final int FLAG_ROC_DPAD_REPEAT = 1 << 8;')
    return source


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    snippet_path = Path(__file__).with_name('RocDpadKeyGuard.java.inc')
    raw = args.source.read_bytes()
    snippet = snippet_path.read_text(encoding='utf-8')
    result = transform(raw.decode('utf-8'), snippet).encode('utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(result)
    digest = lambda value: hashlib.sha256(value).hexdigest()
    print(json.dumps({'source_sha256': digest(raw), 'output_sha256': digest(result),
        'snippet_sha256': digest(snippet_path.read_bytes()), 'original_modified': False,
        'scope': 'four navigation packages only; raw DPAD at ViewPostImeInputStage'}))


if __name__ == '__main__':
    main()
