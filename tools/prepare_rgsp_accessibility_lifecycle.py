"""Make accessibility Binder cleanup idempotent after an early service death."""
import argparse
import hashlib
import json
from pathlib import Path

REL='frameworks/base/services/accessibility/java/com/android/server/accessibility/AbstractAccessibilityServiceConnection.java'
BEFORE='7e6d75f1e644e4c0223e7435b06608a550d47c6aec16b86b593551db20bc0a10'
OLD='''        if (mService != null) {
            mService.unlinkToDeath(this, 0);
            mService = null;
        }'''
NEW='''        if (mService != null) {
            try {
                mService.unlinkToDeath(this, 0);
            } catch (java.util.NoSuchElementException alreadyUnlinked) {
                // A service can die while connection setup is still in flight.
                // Reset must also work if no death recipient remains registered.
            }
            mService = null;
        }'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    target=a.source/REL;old=target.read_text().replace(NEW,OLD,1)
    if hashlib.sha256(old.encode()).hexdigest()!=BEFORE:raise SystemExit('Unrecognized accessibility lifecycle edits; preserved')
    if old.count(OLD)!=1:raise SystemExit('Ambiguous Binder reset anchor')
    after=old.replace(OLD,NEW,1);target.write_bytes(after.encode())
    proof={'status':'PASS_ONLY_ALREADY_UNLINKED_BINDER_RESET_GUARD','source':REL,
        'before_sha256':BEFORE,'after_sha256':hashlib.sha256(after.encode()).hexdigest(),
        'scope':'Only missing death-recipient cleanup becomes idempotent; key dispatch, connection policy, permissions, IME and other services unchanged'}
    (a.source/'out/rgsp-accessibility-lifecycle-inputs.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('ACCESSIBILITY_LIFECYCLE_PREPARED',proof['after_sha256'])


if __name__=='__main__':main()
