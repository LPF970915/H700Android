"""Keep default-link settings usable on devices without the optional widget service."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/apps/Settings/src/com/android/settings/applications/ClearDefaultsPreference.java'
BEFORE='0293059a7027d1e2d5e375c06ab97c0a13e4e0ab2db1ad0f867b4c76920f57f1'
EDITS=[
 ('        mAppWidgetManager = AppWidgetManager.getInstance(context);',
  '''        // AppWidgetService is optional. Looking it up without the feature
        // can trigger SystemServiceRegistry.wtf and kill Settings on this BSP.
        mAppWidgetManager = context.getPackageManager().hasSystemFeature(
                PackageManager.FEATURE_APP_WIDGETS) ? AppWidgetManager.getInstance(context) : null;'''),
 ('                    mAppWidgetManager.setBindAppWidgetPermission(mPackageName, false);',
  '''                    if (mAppWidgetManager != null) {
                        mAppWidgetManager.setBindAppWidgetPermission(mPackageName, false);
                    }'''),
 ('''        boolean hasBindAppWidgetPermission =
                mAppWidgetManager.hasBindAppWidgetPermission(mAppEntry.info.packageName);''',
  '''        boolean hasBindAppWidgetPermission = mAppWidgetManager != null
                && mAppWidgetManager.hasBindAppWidgetPermission(mAppEntry.info.packageName);''')]


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    target=a.source/REL;source=target.read_text();original=source
    if sha(original.encode())!=BEFORE:
        for old,new in reversed(EDITS):original=original.replace(new,old,1)
    if sha(original.encode())!=BEFORE:raise SystemExit('Unexpected clear-defaults edits; preserved')
    patched=original
    for old,new in EDITS:
        if patched.count(old)!=1:raise SystemExit('Ambiguous optional-widget anchor')
        patched=patched.replace(old,new,1)
    target.write_bytes(patched.encode())
    receipt={'status':'PASS_ONLY_DELTA_IS_OPTIONAL_WIDGET_CAPABILITY_AND_NULL_GUARDS',
             'source':REL,'before_sha256':BEFORE,'after_sha256':sha(patched.encode()),
             'scope':'Preferred activities, browser/USB defaults, key routing and navigation layout unchanged'}
    (a.source/'out/rgsp-optional-widget-defaults-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('OPTIONAL_WIDGET_DEFAULTS_PREPARED',receipt['after_sha256'])


if __name__=='__main__':main()
