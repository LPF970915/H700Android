"""Give Android10's handheld role pages a real ActionBar on TV configurations."""
import argparse
import hashlib
import json
from pathlib import Path

BASE='packages/apps/PermissionController/'
ACTIVITY='src/com/android/packageinstaller/role/ui/'
ANCHOR='''            setTheme(R.style.CarSettings);
        }
        super.onCreate(savedInstanceState);'''
REPLACEMENT='''            setTheme(R.style.CarSettings);
        } else if (DeviceUtils.isTelevision(this)) {
            // These role pages use handheld fragments even in TV mode. The
            // normal TV Settings theme is Leanback and has no native ActionBar.
            setTheme(R.style.RgspRoleSettings);
        }
        super.onCreate(savedInstanceState);'''
STYLE='''
    <!-- The role activities render handheld preference fragments on TV too. -->
    <style name="RgspRoleSettings" parent="@android:style/Theme.DeviceDefault.Settings">
        <item name="android:windowActionBar">true</item>
        <item name="android:windowNoTitle">false</item>
        <item name="preferenceTheme">@style/PreferenceThemeOverlay</item>
        <item name="preferenceCategoryTitleTextAppearance">@style/TextAppearance.CategoryTitle</item>
    </style>
'''
EDITS={
 ACTIVITY+'DefaultAppActivity.java':('1fa7930d5160422bc7fc2f0592ac7cb4acb3b50c15726e3df0a5df08e987d897',[(ANCHOR,REPLACEMENT)]),
 ACTIVITY+'DefaultAppListActivity.java':('9dde9acdb8f53382d914402893a7d77891f794fb31de8bed97f7aeb67bebea40',[(ANCHOR,REPLACEMENT)]),
 ACTIVITY+'handheld/SettingsFragment.java':('3b1684ded81b8af87cd017eaf59864706fdbc0a797f50b92e9c57040ffc34afe',[
  ('import android.os.Bundle;','import android.app.ActionBar;\nimport android.os.Bundle;'),
  ('        requireActivity().getActionBar().setDisplayHomeAsUpEnabled(true);',
   '''        final ActionBar actionBar = requireActivity().getActionBar();
        if (actionBar != null) {
            actionBar.setDisplayHomeAsUpEnabled(true);
        }''')]),
 'res/values/themes.xml':('1b0551389afec0ca525690e11acfdb9be36b8e909536ae0559407e9a8a45f6f9',[
  ('</resources>',STYLE+'\n</resources>')]),
}


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    ready=[]
    for rel,(expected,edits) in EDITS.items():
        target=a.source/BASE/rel;source=target.read_text();original=source
        if sha(original.encode())!=expected:
            for old,new in reversed(edits):original=original.replace(new,old,1)
        if sha(original.encode())!=expected:raise SystemExit('Unexpected role-settings edits; preserved: '+rel)
        patched=original
        for old,new in edits:
            if patched.count(old)!=1:raise SystemExit('Ambiguous role-settings anchor: '+rel)
            patched=patched.replace(old,new,1)
        ready.append((target,original,patched,rel))
    receipt={'status':'PASS_PINNED_TV_ROLE_THEME_AND_NULL_ACTIONBAR_GUARD_ONLY','sources':{}}
    for target,original,patched,rel in ready:
        target.write_bytes(patched.encode());receipt['sources'][BASE+rel]={'before_sha256':sha(original.encode()),'after_sha256':sha(patched.encode())}
    (a.source/'out/rgsp-role-settings-theme-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('TV_ROLE_SETTINGS_THEME_PREPARED')


if __name__=='__main__':main()
