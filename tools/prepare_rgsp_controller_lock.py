"""Hide touch-only pattern enrollment on the controller-only RGSP product."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/apps/Settings/src/com/android/settings/password/ChooseLockGenericController.java'
BEFORE='a76009c42f860f2b1cd83408ea50746db917b7ecf80fecfa42b5caccccb96a75'
OLD='''    public boolean isScreenLockVisible(ScreenLockType type) {
        final boolean managedProfile'''
NEW='''    public boolean isScreenLockVisible(ScreenLockType type) {
        // Pattern enrollment and the keyguard pattern widget require touch.
        // Retain PIN/password instead of offering an unusable lock method.
        if ("rgsp".equals(android.os.Build.DEVICE) && type == ScreenLockType.PATTERN) {
            return false;
        }
        final boolean managedProfile'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    a=p.parse_args(); target=a.source/REL
    text=target.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE:
        raise SystemExit('Unrecognized lock controller edits; no files changed')
    if base.count(OLD)!=1:raise SystemExit('Ambiguous lock controller anchor')
    patched=base.replace(OLD,NEW,1);target.write_text(patched)
    (a.source/'out/rgsp-controller-lock-inputs.json').write_text(json.dumps(
        {'path':REL,'before':BEFORE,'after':hashlib.sha256(patched.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_CONTROLLER_LOCK_OPTIONS_PREPARED')

if __name__=='__main__':main()
