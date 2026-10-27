#!/usr/bin/env python3
"""Stage native system/vendor outputs and exact baked-component expectations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from android_sparse_to_raw import convert


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--product',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    output=a.output.resolve();product=a.product.resolve()
    if output.exists() or not output.is_relative_to(root/'out'):raise ValueError('New workspace out directory required')
    if shutil.disk_usage(root).free<120*1024**3:raise ValueError('At least 120 GiB free required')
    components={}
    system_files=['system/build.prop','system/framework/framework-res.apk','system/framework/services.jar',
        'system/lib/libsurfaceflinger.so',
        'system/framework/wifi-service.jar',
        'system/product/priv-app/SystemUI/SystemUI.apk','system/product/priv-app/Settings/Settings.apk',
        'system/product/priv-app/SettingsIntelligence/SettingsIntelligence.apk',
        'system/priv-app/SettingsProvider/SettingsProvider.apk','system/priv-app/MediaProvider/MediaProvider.apk',
        'system/app/RGSPNavigation/RGSPNavigation.apk','system/priv-app/AT4K/AT4K.apk',
        'system/app/LeanbackIME/LeanbackIME.apk','system/etc/rgsp/leanback.sha256',
        'system/product/app/LatinIME/LatinIME.apk',
        'system/product/app/Calendar/Calendar.apk',
        'system/priv-app/DocumentsUI/DocumentsUI.apk','system/bin/adbd','system/bin/vold',
        'system/priv-app/PermissionController/PermissionController.apk',
        'system/app/Traceur/Traceur.apk','system/priv-app/PackageInstaller/PackageInstaller.apk',
        'system/product/priv-app/Contacts/Contacts.apk',
        'system/bin/rgsp-wifi-adb-session.sh','system/bin/rgsp-roms-handoff.sh',
        'system/bin/rgsp-firstboot.sh','system/bin/set_rgsp_home.sh','system/etc/init/rgsp-firstboot.rc',
        'system/bin/rgsp-navigation-defaults.sh','system/etc/init/rgsp-navigation-defaults.rc',
        'system/etc/init/rgsp-roms-handoff.rc','system/lib/modules/mali_kbase.ko',
        'system/usr/keylayout/ANBERNIC-keys.kl',
        'system/usr/keylayout/Vendor_0001_Product_0001.kl',
        'system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl']
    vendor_files=['etc/permissions/android.hardware.usb.host.xml',
        'etc/permissions/android.hardware.touchscreen.unavailable.xml','etc/fstab.sun50iw9p1',
        'modules/8821cs.ko','lib/egl/libGLES_mali.so','lib/hw/hwcomposer.cupid.so','etc/dispconfigs/h700-rgsp-lcd.json']
    for name in system_files:components['system:/'+name]=sha(product/name)
    if (product/'system/etc/rgsp/leanback.sha256').read_text().strip()!=sha(product/'system/app/LeanbackIME/LeanbackIME.apk'):
        raise ValueError('Factory IME provisioning hash is stale; rebuild systemimage')
    for name in vendor_files:components['vendor:/'+name]=sha(product/'vendor'/name)
    for name in ('system.img','vendor.img'):
        if not (product/name).is_file():raise ValueError('Missing native image: '+name)
    output.mkdir()
    (output/'components.json').write_text(json.dumps(components,indent=2)+'\n')
    images={}
    for name,length in [('system',8589934592),('vendor',2147483648)]:
        print('STAGE '+name,flush=True)
        source=product/(name+'.img');sparse=output/(name+'.img');raw=output/(name+'.raw.img')
        shutil.copyfile(source,sparse);convert(str(sparse),str(raw))
        if raw.stat().st_size!=length:raise ValueError('Unexpected raw partition size: '+name)
        check=subprocess.run(['e2fsck','-f','-n',str(raw)],capture_output=True,text=True)
        (output/(name+'.fsck.txt')).write_text(check.stdout+check.stderr)
        if check.returncode:raise ValueError('Read-only filesystem check failed: '+name)
        images[name]={'sparse_sha256':sha(sparse),'raw_sha256':sha(raw),'e2fsck_exit':0}
    source=product.parents[3]
    inputs=['system/core/adb/daemon/main.cpp',
        'frameworks/base/services/accessibility/java/com/android/server/accessibility/AbstractAccessibilityServiceConnection.java',
        'packages/apps/Settings/src/com/android/settings/widget/VideoPreference.java',
        'packages/apps/Settings/res/values/config_video_previews.xml',
        'device/roc/rgsp/overlay/packages/apps/Settings/res/values/bools.xml',
        'packages/apps/SettingsIntelligence/src/com/android/settings/intelligence/search/SearchFragment.java',
        'packages/apps/SettingsIntelligence/src/com/android/settings/intelligence/search/SearchActivity.java',
        'packages/apps/PermissionController/src/com/android/packageinstaller/role/ui/DefaultAppActivity.java',
        'packages/apps/PermissionController/src/com/android/packageinstaller/role/ui/DefaultAppListActivity.java',
        'packages/apps/PermissionController/src/com/android/packageinstaller/role/ui/handheld/SettingsFragment.java',
        'packages/apps/PermissionController/res/values/themes.xml',
        'packages/inputmethods/LatinIME/java/src/com/android/inputmethodcommon/InputMethodSettingsImpl.java',
        'packages/inputmethods/LatinIME/java/src/com/android/inputmethod/latin/settings/CustomInputStylePreference.java',
        'packages/inputmethods/LeanbackIME/src/com/android/inputmethod/leanback/service/LeanbackImeService.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/base/Shared.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/base/RgspFileNameDialog.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/dirlist/RenameDocumentFragment.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/CreateDirectoryFragment.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/GridItemThumbnail.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/dirlist/AccessibilityEventRouter.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/NavigationViewManager.java',
        'packages/apps/DocumentsUI/src/com/android/documentsui/files/FilesActivity.java',
        'packages/apps/Calendar/src/com/android/calendar/widget/CalendarAppWidgetProvider.java',
        'packages/apps/Calendar/src/com/android/calendar/widget/CalendarAppWidgetService.java',
        'packages/providers/MediaProvider/src/com/android/providers/media/MediaProvider.java',
        'packages/apps/Settings/src/com/android/settings/core/SettingsBaseActivity.java',
        'packages/apps/Settings/src/com/android/settings/applications/ClearDefaultsPreference.java',
        'packages/apps/Settings/src/com/android/settings/password/ChooseLockGenericController.java',
        'packages/apps/Settings/src/com/android/settings/localepicker/LocaleDragAndDropAdapter.java',
        'packages/apps/Settings/src/com/android/settings/core/RgspDpadMenuBridge.java',
        'packages/apps/Settings/src/com/android/settings/core/RgspDpadDialogPolicy.java',
        'packages/apps/Settings/src/com/android/settings/homepage/SettingsHomepageActivity.java',
        'packages/apps/Settings/src/com/android/settings/bluetooth/BluetoothFilesPreferenceController.java',
        'frameworks/base/services/java/com/android/server/SystemServer.java',
        'frameworks/base/services/core/java/com/android/server/oemlock/OemLockService.java',
        'frameworks/base/services/core/java/com/android/server/oemlock/RgspUnsupportedOemLock.java',
        'frameworks/base/services/core/java/com/android/server/inputmethod/InputMethodManagerService.java',
        'frameworks/opt/net/wifi/service/java/com/android/server/wifi/ClientModeImpl.java',
        'frameworks/base/packages/SystemUI/src/com/android/systemui/statusbar/phone/StatusBarWindowView.java',
        'frameworks/base/packages/SystemUI/src/com/android/systemui/globalactions/GlobalActionsDialog.java',
        'frameworks/native/services/surfaceflinger/DisplayHardware/FramebufferSurface.cpp',
        'hardware/aw/hwc2/hwc.cpp',
        'hardware/aw/hwc2/de2family/DisplayOpr.cpp',
        'hardware/aw/hwc2/de2family/RgspFramePeriod.h',
        'hardware/aw/hwc2/threadResouce/hwc_event_thread.cpp']
    fingerprints={name:sha(source/name) for name in inputs}
    for path in (source/'device/roc/rgsp').rglob('*'):
        if path.is_file() and path.suffix in ('.java','.xml','.mk','.sh','.rc','.prop','.c','.h'):
            fingerprints[path.relative_to(source).as_posix()]=sha(path)
    (output/'source-proof.json').write_text(json.dumps(fingerprints,indent=2)+'\n')
    (output/'STAGING_MANIFEST.json').write_text(json.dumps({'product':str(product),'images':images,
        'components_sha256':sha(output/'components.json'),'source_proof_sha256':sha(output/'source-proof.json'),
        'writes_to_device':False},indent=2)+'\n')
    print('STAGED_NATIVE_V5G_INPUTS',flush=True)


if __name__=='__main__':main()
