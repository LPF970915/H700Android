"""Restore existing custom-input-style selections by value instead of identity."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/inputmethods/LatinIME/java/src/com/android/inputmethod/latin/settings/CustomInputStylePreference.java'
BEFORE='6291971071653954899edf041f0330752af3252a7fb1cd61bb71a5f19754bc21'
OLD='''            if (item.equals(itemToSelect)) {
                spinner.setSelection(i);
                return;
            }'''
NEW='''            // The selection key is a newly constructed value object. These
            // adapter items do not implement Object.equals, so identity matching
            // leaves an existing style at the first language/layout instead.
            final boolean sameLocale = item instanceof SubtypeLocaleItem
                    && itemToSelect instanceof SubtypeLocaleItem
                    && ((SubtypeLocaleItem) item).compareTo((SubtypeLocaleItem) itemToSelect) == 0;
            final boolean sameLayout = item instanceof KeyboardLayoutSetItem
                    && itemToSelect instanceof KeyboardLayoutSetItem
                    && ((KeyboardLayoutSetItem) item).mLayoutName.equals(
                            ((KeyboardLayoutSetItem) itemToSelect).mLayoutName);
            if (sameLocale || sameLayout) {
                spinner.setSelection(i);
                return;
            }'''


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    target=a.source/REL;source=target.read_text();original=source.replace(NEW,OLD,1)
    if sha(original.encode())!=BEFORE:raise SystemExit('Unexpected custom-input-style edits; preserved')
    if original.count(OLD)!=1:raise SystemExit('Ambiguous selection restore anchor')
    patched=original.replace(OLD,NEW,1);target.write_bytes(patched.encode())
    receipt={'status':'PASS_ONLY_DELTA_IS_VALUE_BASED_LOCALE_AND_LAYOUT_SELECTION_RESTORE',
             'source':REL,'before_sha256':BEFORE,'after_sha256':sha(patched.encode()),
             'unchanged':'All other LatinIME source; no key routing, IME lifecycle, or preference-write changes'}
    (a.source/'out/rgsp-latin-style-restore-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('LATIN_STYLE_SELECTION_RESTORE_PREPARED',receipt['after_sha256'])


if __name__=='__main__':main()
