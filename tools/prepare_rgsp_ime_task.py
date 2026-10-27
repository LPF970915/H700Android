"""Keep the RGSP keyboard language page in its caller's back stack."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/inputmethods/LatinIME/java/src/com/android/inputmethodcommon/InputMethodSettingsImpl.java'
BEFORE='bda195fb72c449958a2644561fc8f8d3c36fb36ada54c6d3f9cefe7191f0756f'
OLD='''        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED
                | Intent.FLAG_ACTIVITY_CLEAR_TOP);'''
NEW='''        // A settings Activity already supplies a valid task. Reusing Settings'
        // task with CLEAR_TOP discards the keyboard settings that launched us.
        if (!"rgsp".equals(android.os.Build.DEVICE)
                || !(context instanceof android.app.Activity)) {
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                    | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED
                    | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        }'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();target=a.source/REL
    text=target.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE:
        raise SystemExit('Unrecognized InputMethodSettingsImpl edits; no files changed')
    if base.count(OLD)!=1:raise SystemExit('Ambiguous IME task anchor')
    patched=base.replace(OLD,NEW,1);target.write_text(patched)
    proof={'path':REL,'before':BEFORE,'after':hashlib.sha256(patched.encode()).hexdigest()}
    (a.source/'out/rgsp-ime-task-inputs.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('RGSP_IME_CALLER_TASK_PREPARED')


if __name__=='__main__':main()
