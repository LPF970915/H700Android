"""Give the RGSP Settings search toolbar an explicit native exit callback."""
import argparse
import hashlib
import json
from pathlib import Path

REL = 'packages/apps/SettingsIntelligence/src/com/android/settings/intelligence/search/SearchFragment.java'
BEFORE = '0651021c3f7c4a3cfb6670e2efe11a95658f023c67d0d7007a01177ae7e2b929'
OLD = '        activity.getActionBar().setDisplayHomeAsUpEnabled(true);'
NEW = OLD + '''
        if ("rgsp".equals(android.os.Build.DEVICE)) {
            // This search page has no parent navigation stack of its own.
            // Keep toolbar Up independent of ActionBar menu-prepared dispatch.
            toolbar.setNavigationOnClickListener(v -> activity.finish());
        }'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    path = args.source / REL
    text = path.read_text()
    baseline = text.replace(NEW, OLD, 1)
    if hashlib.sha256(baseline.encode()).hexdigest() != BEFORE or baseline.count(OLD) != 1:
        raise SystemExit('Unrecognized Settings search source; preserved')
    result = baseline.replace(OLD, NEW, 1)
    if text != result:
        path.write_bytes(result.encode())
    (args.source / 'out/rgsp-settings-search-inputs.json').write_text(json.dumps({
        REL: hashlib.sha256(result.encode()).hexdigest(),
    }, indent=2) + '\n')
    print('RGSP_NATIVE_SETTINGS_SEARCH_UP_CALLBACK_PREPARED')


if __name__ == '__main__':
    main()
