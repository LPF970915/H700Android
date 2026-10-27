"""Preserve the selected controller IME across RGSP locale changes."""
import argparse,hashlib,json
from pathlib import Path

REL='frameworks/base/services/core/java/com/android/server/inputmethod/InputMethodManagerService.java'
BEFORE='88f99d3d4b74f9a8382dd5ccf34174b4b1257fd69f6fdbed72101d73e0c9114e'
OLD='''            buildInputMethodListLocked(true);
            // If the locale is changed, needs to reset the default ime
            resetDefaultImeLocked(mContext);
            updateFromSettingsLocked(true);
            mLastSystemLocales = possibleNewLocale;'''
NEW='''            final String selectedIme = mSettings.getSelectedInputMethod();
            final boolean keepControllerIme = "rgsp".equals(android.os.Build.DEVICE)
                    && "com.android.inputmethod.leanback/.service.LeanbackImeService".equals(
                            selectedIme)
                    && mMethodMap.containsKey(selectedIme)
                    && mSettings.getEnabledInputMethodListLocked().contains(
                            mMethodMap.get(selectedIme));
            buildInputMethodListLocked(true);
            // A locale change must not replace the usable controller keyboard.
            // Preserve normal fallback if that IME has disappeared or was disabled.
            if (!keepControllerIme || !mMethodMap.containsKey(selectedIme)) {
                resetDefaultImeLocked(mContext);
            }
            updateFromSettingsLocked(true);
            mLastSystemLocales = possibleNewLocale;'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    path=a.source/REL;text=path.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE or base.count(OLD)!=1:
        raise SystemExit('Unrecognized IMMS changes; preserved')
    result=base.replace(OLD,NEW,1)
    if result!=text:path.write_text(result)
    (a.source/'out/rgsp-locale-ime-inputs.json').write_text(json.dumps({REL:hashlib.sha256(result.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_LOCALE_CONTROLLER_IME_PREPARED')

if __name__=='__main__':main()
