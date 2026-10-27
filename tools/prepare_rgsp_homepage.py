#!/usr/bin/env python3
"""Match homepage content padding to the RGSP fixed-header product layout."""
import argparse
import hashlib
from pathlib import Path

REL='packages/apps/Settings/src/com/android/settings/homepage/SettingsHomepageActivity.java'
BEFORE='33c8a11bf7363678aaac17a3365caa298385d843faca3cc04d92c5ea8ba664f8'
OLD='        final int paddingTop = searchBarHeight + searchBarMargin * 2;'
NEW='''        // RGSP uses a real fixed header above its scroll viewport.
        final int paddingTop = "rgsp".equals(android.os.Build.DEVICE)
                ? 0 : searchBarHeight + searchBarMargin * 2;'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();path=a.source/REL
    data=path.read_bytes();text=data.decode();original=text.replace(NEW,OLD)
    if hashlib.sha256(original.encode()).hexdigest()!=BEFORE or original.count(OLD)!=1:
        raise SystemExit('Unrecognized homepage edits; no source changed')
    patched=original.replace(OLD,NEW).encode()
    if data==patched:print('ALREADY_APPLIED')
    else:path.write_bytes(patched);print('RGSP_FIXED_HEADER_PADDING_APPLIED')


if __name__=='__main__':main()
