#!/usr/bin/env python3
"""Package new system/vendor files over a pinned v5f image; never open a card."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

BASE_SHA='fed34834be77931bc38f1bf925bf66451c242c2b5dc6bde75e7a107e55be21bb'
SIZE=32434554368
SYSTEM=(222298112,8589934592)
VENDOR=(8812232704,2147483648)
PINNED_COMPONENTS={
    'system:/system/priv-app/AT4K/AT4K.apk':'b2fa0343e903ad01c3854999dba70335ba4df5f5522dd931ed9d7189cf841a7d',
    'system:/system/app/LeanbackIME/LeanbackIME.apk':'6f29e76aeb91d5caba1690325f9e4dd22d29f2f1acd713dd14f95f3c867e2efd',
    'system:/system/bin/vold':'9869fa1e7c4f9584504ef8ffa407381fd9236d711b7b917bd3bab6cb02d012ce',
    'system:/system/lib/modules/mali_kbase.ko':'987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9',
    'system:/system/usr/keylayout/ANBERNIC-keys.kl':'99b729a799e47db82a389527e4cc232e186d4a1c431f119326fb093a9def9056',
    'system:/system/usr/keylayout/Vendor_0001_Product_0001.kl':'99b729a799e47db82a389527e4cc232e186d4a1c431f119326fb093a9def9056',
    'system:/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl':'99b729a799e47db82a389527e4cc232e186d4a1c431f119326fb093a9def9056',
    'system:/system/product/priv-app/SystemUI/SystemUI.apk':'0232e8f434267406881c44746be5b0d0ac3c713ee101ba69e3b542a33dbd6e78',
    'system:/system/framework/services.jar':'7015b60d93e1b516378cf91b691cc628305ba37ec7cc872013babf5e8159bff5',
    'vendor:/etc/permissions/android.hardware.usb.host.xml':'201da252a1ed52d5d1019412900d7a1cb530afb4558f9f1ba3d124189a1f9819',
    'vendor:/etc/permissions/android.hardware.touchscreen.unavailable.xml':'35a31dc53804a48aaf354890edf4fc7792bba8093deb9291e48ba4d939f095c2',
    'system:/system/bin/adbd':'958fc1252bdc75c01d4915f87d08a57dbe2a894dc175b8e825e1a0067a8028a0',
}


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def copy_range(source,destination,offset,count):
    source.seek(offset)
    digest=hashlib.sha256()
    while count:
        block=source.read(min(count,8*1024*1024))
        if not block:raise ValueError('Short image input')
        digest.update(block)
        # Preserve sparseness of the baseline's empty factory userdata.
        if block.count(0)==len(block):destination.seek(len(block),1)
        else:destination.write(block)
        count-=len(block)
    return digest.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--baseline-manifest',type=Path,required=True)
    p.add_argument('--system',type=Path,required=True)
    p.add_argument('--vendor',type=Path,required=True)
    p.add_argument('--components',type=Path,required=True,
                   help='JSON mapping system/vendor absolute image paths to expected SHA-256')
    p.add_argument('--staging-manifest',type=Path,
                   help='Pin the exact native stage, including full raw partitions and source/component receipts')
    p.add_argument('--validation-report',type=Path,required=True,
                   help='Completed reachability report with exact tested component hashes')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--aapt2',type=Path,required=True)
    p.add_argument('--navigation-version',type=int,required=True,
                   help='Exact tested native navigation implementation to require inside the image')
    a=p.parse_args()
    for f in (a.baseline,a.system,a.vendor,a.baseline_manifest,a.components,a.validation_report):
        if not stat.S_ISREG(f.lstat().st_mode):raise ValueError('Regular local inputs only: '+str(f))
    root=Path(__file__).resolve().parents[1]
    output=a.output.resolve()
    if not output.is_relative_to(root/'out'):raise ValueError('Output must stay inside workspace out')
    partial=output.with_suffix('.partial')
    receipt=output.with_suffix('.json')
    if any(f.exists() for f in (output,partial,receipt)):raise ValueError('New output names required')
    if shutil.disk_usage(output.parent).free<50*1024**3:raise ValueError('At least 50 GiB free required')
    if a.baseline.stat().st_size!=SIZE:raise ValueError('Unexpected v5f size')
    manifest=json.loads(a.baseline_manifest.read_text())
    if manifest['sha256']!=BASE_SHA:raise ValueError('Unrecognized baseline manifest')
    print('VERIFY_BASELINE_HASH',flush=True)
    if sha(a.baseline)!=BASE_SHA:raise ValueError('v5f baseline hash mismatch')
    artifacts={}
    components=json.loads(a.components.read_text())
    staging=None
    if a.staging_manifest:
        staging=json.loads(a.staging_manifest.read_text())
        if a.staging_manifest.resolve().parent!=a.components.resolve().parent:
            raise ValueError('Stage manifest and components must belong to the same stage')
        if sha(a.components)!=staging['components_sha256']:
            raise ValueError('Staged component receipt changed')
        if sha(a.components.parent/'source-proof.json')!=staging['source_proof_sha256']:
            raise ValueError('Staged source receipt changed')
    for key,digest in PINNED_COMPONENTS.items():
        if key in components and components[key]!=digest:raise ValueError('Pinned component changed: '+key)
        components[key]=digest
    for required in ('system:/system/framework/services.jar',
                     'system:/system/lib/libsurfaceflinger.so',
                     'system:/system/framework/wifi-service.jar',
                     'system:/system/build.prop',
                     'system:/system/bin/adbd',
                     'system:/system/app/RGSPNavigation/RGSPNavigation.apk',
                     'system:/system/product/priv-app/Settings/Settings.apk',
                     'system:/system/product/priv-app/SettingsIntelligence/SettingsIntelligence.apk',
                     'system:/system/product/priv-app/SystemUI/SystemUI.apk',
                     'system:/system/framework/framework-res.apk',
                     'system:/system/priv-app/SettingsProvider/SettingsProvider.apk',
                     'system:/system/priv-app/MediaProvider/MediaProvider.apk',
                     'system:/system/priv-app/DocumentsUI/DocumentsUI.apk',
                     'system:/system/priv-app/PermissionController/PermissionController.apk',
                     'system:/system/product/app/LatinIME/LatinIME.apk',
                     'system:/system/product/app/Calendar/Calendar.apk',
                     'system:/system/app/LeanbackIME/LeanbackIME.apk',
                     'system:/system/etc/rgsp/leanback.sha256',
                     'system:/system/bin/rgsp-wifi-adb-session.sh',
                     'system:/system/bin/rgsp-firstboot.sh',
                     'system:/system/bin/set_rgsp_home.sh',
                     'system:/system/etc/init/rgsp-firstboot.rc',
                     'system:/system/bin/rgsp-navigation-defaults.sh',
                     'system:/system/etc/init/rgsp-navigation-defaults.rc',
                     'vendor:/etc/permissions/android.hardware.usb.host.xml',
                     'vendor:/lib/hw/hwcomposer.cupid.so'):
        if required not in components:raise ValueError('Missing required baked component: '+required)
    validation=json.loads(a.validation_report.read_text())
    if validation.get('status')!='SOFTWARE_REACHABILITY_COMPLETE_PENDING_PHYSICAL_TEST':
        raise ValueError('Software reachability audit is not complete')
    if validation.get('unresolved_navigation_failures') or validation.get('remaining_software_tests'):
        raise ValueError('Unresolved navigation tests remain')
    if validation.get('no_touch_capability',{}).get('runtime_touchscreen_feature') is not False:
        raise ValueError('The no-touch policy has not been verified after reboot')
    tested=validation.get('tested_components',{})
    for key in ('system:/system/product/priv-app/Settings/Settings.apk',
                'system:/system/lib/libsurfaceflinger.so',
                'system:/system/product/priv-app/SettingsIntelligence/SettingsIntelligence.apk',
                'system:/system/app/RGSPNavigation/RGSPNavigation.apk',
                'system:/system/framework/services.jar',
                'system:/system/framework/wifi-service.jar',
                'system:/system/product/priv-app/SystemUI/SystemUI.apk',
                'system:/system/app/LeanbackIME/LeanbackIME.apk',
                'system:/system/product/app/LatinIME/LatinIME.apk',
                'system:/system/priv-app/DocumentsUI/DocumentsUI.apk',
                'system:/system/priv-app/PermissionController/PermissionController.apk',
                'vendor:/lib/hw/hwcomposer.cupid.so'):
        if tested.get(key)!=components[key]:
            raise ValueError('Image differs from tested device component: '+key)
    for name,image,(_,length) in [('system',a.system,SYSTEM),('vendor',a.vendor,VENDOR)]:
        if image.stat().st_size!=length:raise ValueError('Wrong raw partition length: '+name)
        subprocess.run(['e2fsck','-f','-n',str(image)],check=True)
        with tempfile.TemporaryDirectory(prefix='v5g-component-check-') as temp:
            checked={}
            for key,digest in components.items():
                if not key.startswith(name+':/'):continue
                inside=key.split(':',1)[1]
                if '..' in Path(inside).parts:raise ValueError('Invalid component path')
                extracted=Path(temp)/'component'
                subprocess.run(['debugfs','-R',f'dump {inside} {extracted}',str(image)],check=True,
                               stdout=subprocess.DEVNULL)
                if not extracted.exists() or sha(extracted)!=digest:raise ValueError('Baked component mismatch: '+key)
                expected={}
                if inside=='/system/lib/libsurfaceflinger.so':
                    if b'Retaining startup allocator buffer for RGSP LCD' not in extracted.read_bytes():
                        raise ValueError('Startup client-target reserve is missing from SurfaceFlinger')
                if inside=='/lib/hw/hwcomposer.cupid.so':
                    content=extracted.read_bytes()
                    if b'RGSP_CLIENT_META_V3' in content or b'RGSP_METADATA_DIAG' in content:
                        raise ValueError('Temporary HWC metadata logger must not ship')
                if inside=='/system/build.prop':
                    if not re.search(r'^ro.product.locale=zh-CN$',extracted.read_text(),re.M):
                        raise ValueError('Factory default locale is not Simplified Chinese')
                if inside=='/system/bin/rgsp-firstboot.sh':
                    content=extracted.read_text()
                    if 'ime list -s |' in content or 'ime list -a -s |' not in content:
                        raise ValueError('Factory IME still checks only enabled methods')
                if inside.endswith('/framework-res.apk'):
                    expected={'integer/config_defaultUiModeType':'4',
                              'integer/config_overrideHasPermanentMenuKey':'2',
                              'bool/config_hasPermanentDpad':'true',
                              'bool/config_defaultInTouchMode':'false'}
                elif inside.endswith('/Settings.apk'):
                    expected={'bool/config_show_encryption_and_credentials_encryption_status':'false',
                              'bool/config_enable_settings_video_previews':'false'}
                    tree=subprocess.check_output([str(a.aapt2),'dump','xmltree',str(extracted),
                        '--file','res/layout/settings_homepage_container.xml'],text=True)
                    if 'CoordinatorLayout' in tree or 'FloatingAppBarScrollingViewBehavior' in tree:
                        raise ValueError('Old floating homepage layout is still baked')
                elif inside.endswith('/SettingsProvider.apk'):
                    expected={'bool/def_show_ime_with_hard_keyboard':'true'}
                if expected:
                    resources=subprocess.check_output([str(a.aapt2),'dump','resources',str(extracted)],text=True)
                    for resource,value in expected.items():
                        if not re.search(r'resource [^\n]+ '+re.escape(resource)+r'\n\s+\(\) '+value+r'\b',resources):
                            raise ValueError('Baked resource mismatch: '+resource)
                    if inside.endswith('/framework-res.apk'):
                        once=re.search(r'resource (0x[0-9a-f]+) id/button_once\b',resources)
                        resolver=re.search(r'resource (0x[0-9a-f]+) id/resolver_list\b',resources)
                        if not once or not resolver:raise ValueError('Missing resolver focus IDs')
                        for layout,direction in [('resolver_list.xml','Down'),('resolver_list_with_default.xml','Up')]:
                            tree=subprocess.check_output([str(a.aapt2),'dump','xmltree',str(extracted),'--file','res/layout/'+layout],text=True)
                            list_section=re.search(r'E: ListView[^\n]*\n(.*?)(?=\n\s*E:|\Z)',tree,re.S)
                            if not list_section or not re.search(r'nextFocus'+direction+r'[^\n]*=@'+re.escape(once[1]),list_section[1]):
                                raise ValueError('Resolver list cannot reach confirmation: '+layout)
                            if 'RGSP_FOCUS_LAYOUT_PROBE' in tree:raise ValueError('Diagnostic marker baked into resolver')
                if inside.endswith('/RGSPNavigation.apk'):
                    with zipfile.ZipFile(extracted) as z:
                        if ('navigationVersion='+str(a.navigation_version)+' mode=').encode() not in z.read('classes.dex'):
                            raise ValueError('Expected navigation implementation v'+str(a.navigation_version))
                if inside.endswith('/etc/rgsp/leanback.sha256'):
                    if extracted.read_text().strip()!=PINNED_COMPONENTS['system:/system/app/LeanbackIME/LeanbackIME.apk']:
                        raise ValueError('Factory provisioning expects a different IME APK')
                checked[inside]=digest;extracted.unlink()
            if not checked:raise ValueError('No component checks for '+name)
        artifacts[name]={'sha256':sha(image),'components':checked}
        if staging and artifacts[name]['sha256']!=staging['images'][name]['raw_sha256']:
            raise ValueError('Raw partition differs from the pinned native stage: '+name)
    ranges=[]
    with partial.open('xb') as dst:
        for name,path,source_offset,dest_offset,count in [
            ('prefix',a.baseline,0,0,SYSTEM[0]),
            ('system',a.system,0,SYSTEM[0],SYSTEM[1]),
            ('vendor',a.vendor,0,VENDOR[0],VENDOR[1]),
            ('factory_data_roms_gpt',a.baseline,VENDOR[0]+VENDOR[1],VENDOR[0]+VENDOR[1],SIZE-VENDOR[0]-VENDOR[1])]:
            print('COPY',name,flush=True);dst.seek(dest_offset)
            with path.open('rb') as src:digest=copy_range(src,dst,source_offset,count)
            ranges.append({'name':name,'offset':dest_offset,'bytes':count,'sha256':digest})
        dst.truncate(SIZE)
    # Re-read all ranges from the result; this also verifies boot/GPT/userdata preservation.
    with partial.open('rb') as f:
        for entry in ranges:
            f.seek(entry['offset']);h=hashlib.sha256();left=entry['bytes']
            while left:
                block=f.read(min(left,8*1024*1024))
                if not block:raise ValueError('Short output')
                h.update(block);left-=len(block)
            if h.hexdigest()!=entry['sha256']:raise ValueError('Output readback mismatch: '+entry['name'])
    result={'release':output.stem,'status':'PACKAGED_COMPONENTS_AND_FILESYSTEMS_VERIFIED_PENDING_PHYSICAL_TEST',
            'image':output.name,'image_bytes':SIZE,'sha256':sha(partial),'baseline_sha256':BASE_SHA,
            'partitions':manifest['partitions'],'ranges':ranges,'artifacts':artifacts,
            'physical_boot_verified':False,'physical_card_writes':False,'persistent_tcp_adb':False,
            'validation_report':a.validation_report.name,
            'validation_report_sha256':sha(a.validation_report),
            'known_issues':validation.get('known_issues',[]),
            'physical_tests_remaining':validation.get('physical_tests_remaining',[]),
            'scope_exclusions':validation.get('scope_exclusions',[])}
    if a.staging_manifest:
        result['staging_manifest']={'file':str(a.staging_manifest),
                                    'sha256':sha(a.staging_manifest)}
    partial.rename(output)
    receipt.write_text(json.dumps(result,indent=2)+'\n')
    print('CANDIDATE_READY '+str(output),flush=True)


if __name__=='__main__':main()
