"""Apply the RGSP-only shared Toolbar fallback to the verified local Settings source."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REL='packages/apps/Settings/src/com/android/settings/core/SettingsBaseActivity.java'
BEFORE='da88abafae5154f3829af7716cb9d56fb207570d2d30ab81fa97757934a99ba0'
MANIFEST_BEFORE='6fba18fb88207a80355617afaa4319e3add56ad49a2f7804e907b87c13f25f93'
BLUETOOTH_REL='packages/apps/Settings/src/com/android/settings/bluetooth/BluetoothFilesPreferenceController.java'
BLUETOOTH_BEFORE='87240c5b0033a9aa40d4e9ab4869c87b8ea24130e2c28f5f1a708c36c7c5cab8'
BLUETOOTH_OLD='''        return mContext.getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)
                ? AVAILABLE'''
BLUETOOTH_NEW='''        return mContext.getPackageManager().hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)
                && (!"rgsp".equals(android.os.Build.DEVICE)
                    || new Intent(ACTION_OPEN_FILES).resolveActivity(mContext.getPackageManager()) != null)
                ? AVAILABLE'''
PROVIDER_PREVIOUS='''        <!-- AndroidX's prebuilt manifest has a library-wide authority. Give this
             application its own name so Settings updates do not collide with SystemUI. -->
        <provider android:name="androidx.lifecycle.ProcessLifecycleOwnerInitializer"
            android:authorities="com.android.settings.lifecycle-process"
            android:exported="false" android:multiprocess="true" />

'''
PROVIDER=PROVIDER_PREVIOUS.replace('<provider android:name=',
    '<provider xmlns:tools="http://schemas.android.com/tools" tools:replace="android:authorities" android:name=')
EDITS=[
 ('public class SettingsBaseActivity extends FragmentActivity {',
  'public class SettingsBaseActivity extends FragmentActivity {\n\n    private RgspDpadMenuBridge mRgspDpadMenus;'),
 ('        setActionBar(toolbar);',
  '        setActionBar(toolbar);\n        if ("rgsp".equals(android.os.Build.DEVICE)) {\n            mRgspDpadMenus = new RgspDpadMenuBridge(this, toolbar);\n        }'),
 ('        super.onResume();',
  '        super.onResume();\n        if (mRgspDpadMenus != null) mRgspDpadMenus.schedule();'),
 ('        super.onPause();',
  '        super.onPause();\n        if (mRgspDpadMenus != null) mRgspDpadMenus.pause();'),
 ('    public void addCategoryListener(CategoryListener listener) {',
  '    @Override\n    protected void onDestroy() {\n        if (mRgspDpadMenus != null) mRgspDpadMenus.close();\n        super.onDestroy();\n    }\n\n    public void addCategoryListener(CategoryListener listener) {'),
 ('    public void addCategoryListener(CategoryListener listener) {',
  '''    @Override
    public void startActivityForResult(android.content.Intent intent, int requestCode,
            android.os.Bundle options) {
        if (!"rgsp".equals(android.os.Build.DEVICE)) {
            super.startActivityForResult(intent, requestCode, options);
            return;
        }
        try {
            super.startActivityForResult(intent, requestCode, options);
        } catch (android.content.ActivityNotFoundException unavailable) {
            android.util.Log.w("Settings", "Unavailable settings activity on RGSP", unavailable);
            android.widget.Toast.makeText(this, com.android.settings.R.string.activity_not_found,
                    android.widget.Toast.LENGTH_SHORT).show();
            if (requestCode >= 0) {
                new android.os.Handler(getMainLooper()).post(() ->
                        onActivityResult(requestCode, RESULT_CANCELED, null));
            }
        }
    }

    public void addCategoryListener(CategoryListener listener) {'''),
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args();target=args.source/REL
    stage_record=args.source/'out/rgsp-settings-navigation-inputs.json'
    previous_inputs=json.loads(stage_record.read_text()) if stage_record.exists() else {}
    bluetooth=args.source/BLUETOOTH_REL
    bluetooth_text=bluetooth.read_text()
    bluetooth_base=bluetooth_text.replace(BLUETOOTH_NEW,BLUETOOTH_OLD,1)
    if hashlib.sha256(bluetooth_base.encode()).hexdigest()!=BLUETOOTH_BEFORE:
        raise SystemExit('Unrecognized Bluetooth controller edits; no files changed')
    bluetooth_patched=bluetooth_base.replace(BLUETOOTH_OLD,BLUETOOTH_NEW,1)
    manifest=args.source/'packages/apps/Settings/AndroidManifest.xml'
    manifest_text=manifest.read_text(encoding='utf-8')
    manifest_base=manifest_text.replace(PROVIDER,'',1).replace(PROVIDER_PREVIOUS,'',1)
    if hashlib.sha256(manifest_base.encode()).hexdigest()!=MANIFEST_BEFORE:
        raise SystemExit('Unrecognized Settings manifest edits; no files changed')
    original=target.read_bytes();text=original.decode()
    reverted=text
    for old,new in reversed(EDITS):
        if new in reverted: reverted=reverted.replace(new,old,1)
    if hashlib.sha256(reverted.encode()).hexdigest()!=BEFORE:
        raise SystemExit('Unrecognized SettingsBaseActivity edits; no files changed')
    patched=reverted
    for old,new in EDITS:
        if patched.count(old)!=1: raise SystemExit('Ambiguous Settings patch anchor')
        patched=patched.replace(old,new,1)
    helper_copies=[]
    for helper in sorted((ROOT/'android/h700-android10/device/roc/rgsp/settings').glob('*.java')):
        dest=target.with_name(helper.name)
        content=helper.read_bytes()
        if dest.exists() and dest.read_bytes()!=content:
            original_menu='00aa32e0db2319ef03bd8a1fdbca5ccc5536e0524fc46c2768b78a37e2f777ae'
            before=hashlib.sha256(dest.read_bytes()).hexdigest()
            known_original=helper.name=='RgspDpadMenuBridge.java' and before==original_menu
            known_staged=previous_inputs.get('SettingsCore/'+helper.name)==before
            if not known_original and not known_staged:
                raise SystemExit('Existing Settings helper differs; no files changed: '+helper.name)
        helper_copies.append((dest,content))
    product=Path('device/roc/rgsp')
    local=ROOT/'android/h700-android10'/product
    inputs=[p for p in (local/'RGSPNavigation').rglob('*') if p.is_file()]
    inputs.extend(local/name for name in (
        'configs/leanback.sha256',
        'overlay/frameworks/base/core/res/res/values/config.xml',
        'overlay/frameworks/base/core/res/res/layout/resolver_list.xml',
        'overlay/frameworks/base/core/res/res/layout/resolver_list_with_default.xml',
        'overlay/frameworks/base/packages/SettingsProvider/res/values/defaults.xml',
        'overlay/packages/apps/Settings/res/values/bools.xml',
        'overlay/packages/apps/Settings/res/layout/settings_homepage_container.xml',
        'overlay/packages/apps/DocumentsUI/res/layout/dialog_file_name.xml',
        'overlay/packages/apps/DocumentsUI/res/layout/directory_app_bar.xml',
        'overlay/packages/apps/DocumentsUI/res/layout/inspector_activity.xml',
        'overlay/packages/apps/DocumentsUI/res/layout/fragment_directory.xml',
        'overlay/packages/apps/DocumentsUI/res/values/rgsp_controller.xml',
        'overlay/packages/apps/DocumentsUI/res/values-zh-rCN/rgsp_controller.xml'))
    copies=[]
    for path in inputs:
        relative=path.relative_to(local)
        destination=args.source/product/relative
        content=path.read_bytes().replace(b'\r\n',b'\n')
        if destination.exists() and destination.read_bytes()!=content:
            result=subprocess.run(['git','-C',str(ROOT),'show',
                'HEAD:'+path.relative_to(ROOT).as_posix()],capture_output=True)
            baseline_matches=not result.returncode and destination.read_bytes().replace(b'\r\n',b'\n')==result.stdout.replace(b'\r\n',b'\n')
            staged_matches=previous_inputs.get(relative.as_posix())==hashlib.sha256(destination.read_bytes()).hexdigest()
            if not baseline_matches and not staged_matches:
                raise SystemExit('Unrecognized native product edits; no files changed: '+str(relative))
        copies.append((destination,content))
    if original!=patched.encode(): target.write_bytes(patched.encode())
    for dest,content in helper_copies:
        if not dest.exists() or dest.read_bytes()!=content: dest.write_bytes(content)
    patched_manifest=manifest_base.replace('        <!-- This is the longest AndroidManifest.xml ever. -->',
        PROVIDER+'        <!-- This is the longest AndroidManifest.xml ever. -->',1)
    if manifest_text!=patched_manifest: manifest.write_bytes(patched_manifest.encode())
    if bluetooth_text!=bluetooth_patched: bluetooth.write_bytes(bluetooth_patched.encode())
    for destination,content in copies:
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists() or destination.read_bytes()!=content: destination.write_bytes(content)
    stage_record.parent.mkdir(parents=True,exist_ok=True)
    fingerprints={destination.relative_to(args.source/product).as_posix():
        hashlib.sha256(content).hexdigest() for destination,content in copies}
    fingerprints.update({'SettingsCore/'+destination.name:hashlib.sha256(content).hexdigest()
        for destination,content in helper_copies})
    stage_record.write_text(json.dumps(fingerprints,indent=2)+'\n')
    print('Verified RGSP shared navigation, Settings menu bridge and product defaults prepared')

if __name__=='__main__':main()
