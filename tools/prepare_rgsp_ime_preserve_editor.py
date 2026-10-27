"""Prevent TV keyboard startup from deleting selected text or moving the cursor."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/inputmethods/LeanbackIME/src/com/android/inputmethod/leanback/service/LeanbackImeService.java'
BEFORE='841a968f95f71537d9a0fd26e5beee42ba3937a0565bc5640838c95944658bce'
OLD='''            // repost text to get completions
            InputConnection ic = getCurrentInputConnection();
            if (ic != null) {'''
NEW='''            // RGSP must not rewrite the editor merely because the keyboard
            // opens. Text before/after the cursor excludes selected text, so
            // this legacy repost loses that selection and changes the cursor.
            // Existing suggestions are already refreshed above; real typing
            // continues to request completions normally.
            InputConnection ic = getCurrentInputConnection();
            if (ic != null && !"rgsp".equals(android.os.Build.DEVICE)) {'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();target=a.source/REL;text=target.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE:
        raise SystemExit('Unrecognized existing RGSP LeanbackIME edits; no files changed')
    if base.count(OLD)!=1:raise SystemExit('Ambiguous IME repost anchor')
    patched=base.replace(OLD,NEW,1);target.write_text(patched)
    (a.source/'out/rgsp-ime-preserve-editor-inputs.json').write_text(json.dumps(
        {'path':REL,'before':BEFORE,'after':hashlib.sha256(patched.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_IME_EDITOR_PRESERVATION_PREPARED')


if __name__=='__main__':main()
