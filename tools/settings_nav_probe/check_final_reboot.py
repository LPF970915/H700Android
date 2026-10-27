"""Actual controller Restart, A unlock, baked-component and debug-guard checks."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from audit import Audit, OUT, adb
from check_startup_buffer_reserve import read_ready
from explore import Explorer, in_toolbar
from followup import top
from files import focus

PACKAGES={
 'system:/system/product/priv-app/Settings/Settings.apk':'com.android.settings',
 'system:/system/product/priv-app/SettingsIntelligence/SettingsIntelligence.apk':'com.android.settings.intelligence',
 'system:/system/app/RGSPNavigation/RGSPNavigation.apk':'com.roc.rgsp.navtrial',
 'system:/system/product/priv-app/SystemUI/SystemUI.apk':'com.android.systemui',
 'system:/system/app/LeanbackIME/LeanbackIME.apk':'com.android.inputmethod.leanback',
 'system:/system/product/app/LatinIME/LatinIME.apk':'com.android.inputmethod.latin',
 'system:/system/priv-app/DocumentsUI/DocumentsUI.apk':'com.android.documentsui',
 'system:/system/priv-app/PermissionController/PermissionController.apk':'com.android.permissioncontroller',
}
STATIC=('system:/system/lib/libsurfaceflinger.so','system:/system/framework/services.jar',
        'system:/system/framework/wifi-service.jar','vendor:/lib/hw/hwcomposer.cupid.so')
EXTRA_PACKAGES={
 'system:/system/priv-app/SettingsProvider/SettingsProvider.apk':'com.android.providers.settings',
 'system:/system/product/app/Calendar/Calendar.apk':'com.android.calendar',
 'system:/system/app/Traceur/Traceur.apk':'com.android.traceur',
 'system:/system/priv-app/PackageInstaller/PackageInstaller.apk':'com.android.packageinstaller',
 'system:/system/priv-app/MediaProvider/MediaProvider.apk':'com.android.providers.media',
 'system:/system/product/priv-app/Contacts/Contacts.apk':'com.android.contacts',
}
EXTRA_STATIC=('system:/system/framework/framework-res.apk',
              'system:/system/usr/keylayout/ANBERNIC-keys.kl',
              'system:/system/usr/keylayout/Vendor_0001_Product_0001.kl',
              'system:/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true');p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--tag',required=True);p.add_argument('--navigation-version',type=int,required=True)
    p.add_argument('--native-framework',action='store_true',help='Require compiled resources with the legacy experimental RRO disabled')
    args=p.parse_args()
    if not args.execute:p.error('--execute required; this performs one controller-confirmed Restart')
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    target=OUT/('final-reboot-'+args.tag+'.json')
    if target.exists():raise ValueError('Fresh evidence required')
    components=json.loads((args.stage/'components.json').read_text())
    for key in list(PACKAGES)+list(STATIC):
        if key not in components:raise ValueError('Incomplete native stage')
    result={'status':'RUNNING','physical_power_cycle':False,'tested_components':{}}
    a=None;stay=None
    try:
        persist_query=('settings get global development_settings_enabled; '
                       'settings get global adb_enabled; '
                       'settings get secure show_ime_with_hard_keyboard')
        result['developer_usb_ime_before']=read_ready(persist_query).split()
        if result['developer_usb_ime_before']!=['1','1','1']:
            raise RuntimeError('Expected enabled developer/USB/hardware-keyboard IME baseline')
        prior=set(OUT.glob('reboot-*.json'))
        subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name('reboot_check.py')),
                        '--execute','--via-power-menu'],check=True)
        new=set(OUT.glob('reboot-*.json'))-prior
        if len(new)!=1:raise RuntimeError('Ambiguous controller reboot receipt')
        receipt=new.pop();reboot=json.loads(receipt.read_text(encoding='utf8'))
        if reboot['status']!='BOOT_COMPLETED_GUARDED_TRANSPORT_RESTORED' or not reboot['no_implicit_listener']:
            raise RuntimeError('Boot or default TCP policy failed')
        result['controller_reboot']={'file':receipt.name,'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()}
        a=Audit();read_ready('getprop ro.serialno')
        stay=read_ready('settings get global stay_on_while_plugged_in').strip()
        if stay not in ('0','1','2','3','4','5','6','7'):raise RuntimeError('Unexpected stay-awake baseline')
        result['stay_before']=stay
        a.command('svc power stayon true');a.ensure_probe()
        power=a.command('dumpsys power | grep mWakefulness=')
        if 'mWakefulness=Awake' in power:a.command('input keyevent 26')
        elif 'mWakefulness=Asleep' not in power:raise RuntimeError('Unknown power state before unlock test')
        for _ in range(10):
            power=a.command('dumpsys power | grep mWakefulness=')
            if 'mWakefulness=Asleep' in power:break
            time.sleep(.2)
        else:raise RuntimeError('Screen did not lock/sleep')
        result['asleep']=power
        a.key('wake')
        result['keyguard_ui_before']=read_ready('dumpsys activity service com.android.systemui/.SystemUIService')
        result['keyguard_before']=a.snap('final-reboot-before-actual-a',True)[3]
        if (result['keyguard_before']['package']!='com.android.systemui'
                or not re.search(r'^\s*mState=1 \(KGRD\)',result['keyguard_ui_before'],re.M)):
            raise RuntimeError('Actual swipe keyguard not confirmed before A')
        a.key('a')
        for _ in range(10):
            state=a.snap('final-reboot-after-actual-a',True)[3]
            if state['package']=='com.overdevs.at4k':break
            time.sleep(.2)
        else:raise RuntimeError('Actual A did not unlock to launcher')
        result['a_unlocked']=state
        result['keyguard_ui_after']=read_ready('dumpsys activity service com.android.systemui/.SystemUIService')
        if not re.search(r'^\s*mState=0 \(SHD\)',result['keyguard_ui_after'],re.M):raise RuntimeError('Keyguard still showing after A')
        result['components']={}
        for key in list(PACKAGES)+list(STATIC):
            if key in PACKAGES:
                paths=read_ready('pm path '+PACKAGES[key]).strip().splitlines()
                if len(paths)!=1:raise RuntimeError('Ambiguous active APK')
                path=paths[0].removeprefix('package:')
            else:path=key.split(':',1)[1] if key.startswith('system:') else '/vendor'+key.split(':',1)[1]
            sha=read_ready('sha256sum '+path).split()[0]
            result['components'][key]={'path':path,'sha256':sha}
            if sha!=components[key]:raise RuntimeError('Component changed after reboot: '+key)
            result['tested_components'][key]=sha
        # Also pin the factory chooser/language resources, provisioning defaults,
        # Calendar's optional-widget fix and all hardware keylayout aliases.
        result['additional_components']={}
        for key in list(EXTRA_PACKAGES)+list(EXTRA_STATIC):
            if key not in components:raise RuntimeError('Missing additional staged component: '+key)
            if key in EXTRA_PACKAGES:
                paths=read_ready('pm path '+EXTRA_PACKAGES[key]).strip().splitlines()
                if len(paths)!=1:raise RuntimeError('Ambiguous additional active APK')
                path=paths[0].removeprefix('package:')
            else:path=key.split(':',1)[1]
            digest=read_ready('sha256sum '+path).split()[0]
            if digest!=components[key]:raise RuntimeError('Additional persisted component mismatch: '+key)
            result['additional_components'][key]={'path':path,'sha256':digest}
        result['services']=read_ready('service check usb; service check oem_lock')
        if not all('Service '+name+': found' in result['services'] for name in ('usb','oem_lock')):
            raise RuntimeError('Required Binder service not found')
        no_touch='vendor:/etc/permissions/android.hardware.touchscreen.unavailable.xml'
        if no_touch in components:
            result['no_touch_feature']=read_ready('pm has-feature android.hardware.touchscreen || true').strip()
            result['no_touch_policy_sha256']=read_ready('sha256sum /vendor/etc/permissions/android.hardware.touchscreen.unavailable.xml').split()[0]
            if result['no_touch_feature']!='false' or result['no_touch_policy_sha256']!=components[no_touch]:
                raise RuntimeError('No-touch capability policy did not persist')
        result['developer_usb_ime_after']=read_ready(persist_query).split()
        if result['developer_usb_ime_after']!=result['developer_usb_ime_before']:
            raise RuntimeError('Developer/USB/hardware-keyboard IME settings did not persist')
        result['runtime_overlays']=read_ready('cmd overlay list --user 0')
        if args.native_framework:
            if '[x] com.roc.rgsp.dpad.frameworkoverlay' in result['runtime_overlays']:
                raise RuntimeError('Legacy resource trial still overrides the compiled framework')
            result['native_framework_resources']=True
            result['native_resource_proof']='Exact framework-res SHA matched; legacy RRO disabled; compiled resource values/layout edges verified in package gate.'
        elif '[x] com.roc.rgsp.dpad.frameworkoverlay' not in result['runtime_overlays']:
            raise RuntimeError('Existing live D-pad overlay did not remain enabled')
        result['navigation']=read_ready('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        if 'navigationVersion='+str(args.navigation_version)+' mode=' not in result['navigation']:raise RuntimeError('Expected navigation helper not active')
        result['ime']=read_ready('settings get secure default_input_method').strip()
        if result['ime']!='com.android.inputmethod.leanback/.service.LeanbackImeService':raise RuntimeError('TV IME did not persist')
        result['locale']=read_ready('settings get system system_locales').strip()
        if result['locale'].split(',')[0] not in ('zh-CN','zh-Hans-CN'):raise RuntimeError('Chinese locale did not persist')
        result['wifi']=read_ready('dumpsys wifi | grep mWifiInfo')
        if 'Xiaomi_0421' not in result['wifi'] or 'COMPLETED' not in result['wifi']:raise RuntimeError('Wi-Fi did not reconnect')
        result['firewall']=read_ready('iptables -C INPUT -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP && '
                                     'ip6tables -C INPUT -p tcp --dport 5555 -j DROP && echo GUARDED')
        result['mounts']=read_ready("grep -E '^/dev/mmcblk0p[56] ' /proc/mounts")
        if not re.search(r'^/dev/mmcblk0p5 / ext4 ro,',result['mounts'],re.M) or not re.search(r'^/dev/mmcblk0p6 /vendor ext4 ro,',result['mounts'],re.M):
            raise RuntimeError('System/vendor not read-only')
        sf=read_ready('dumpsys SurfaceFlinger');result['reserve_lines']=[l for l in sf.splitlines() if 'RGSP startup allocator reserve' in l]
        if not result['reserve_lines']:raise RuntimeError('Graphics reserve not active after final Restart')
        pid=read_ready('pidof surfaceflinger').strip();logs=read_ready('logcat -d -b all --pid='+pid)
        result['gpu_errors']=[l for l in logs.splitlines() if 'Aborting GPU composition' in l or 'Failed to bind framebuffer' in l or 'Crop rectangle dimensions not equal' in l]
        if result['gpu_errors']:raise RuntimeError('GPU errors after final Restart')
        Explorer(a).goto_root();top(a)
        result['postboot_navigation']={}
        result['postboot_navigation']['network_focus']=focus(a,'网络和互联网',expected_package='com.android.settings')
        a.key('a');network=a.snap('final-reboot-network-entry',True)[3]
        if network['package']!='com.android.settings' or network['window']!='网络和互联网':
            raise RuntimeError('Post-boot controller did not open network settings')
        result['postboot_navigation']['network_entry']=network
        top(a);result['postboot_navigation']['wlan_focus']=focus(a,'WLAN',expected_package='com.android.settings')
        a.key('a');wlan=a.snap('final-reboot-wlan-entry',True)[3]
        if wlan['package']!='com.android.settings' or wlan['window']!='WLAN':
            raise RuntimeError('Post-boot controller did not open WLAN')
        result['postboot_navigation']['wlan_entry']=wlan
        # Complete the root WLAN list itself after reboot. Only direction keys
        # are sent, so an arbitrary discovered/open access point is never joined.
        top(a);walks={};reached=set()
        for direction in ('d','u'):
            states=[];previous=None;repeat=0
            for _ in range(160):
                _,root,_,state=a.snap('final-reboot-wlan-walk-'+direction)
                if state['window_id']!=wlan['window_id']:raise RuntimeError('Direction left the WLAN root')
                states.append(state);reached.add(state.get('focus'))
                key=state['focus_signature'];repeat=repeat+1 if key==previous else 0
                if repeat>=2:break
                previous=key;a.key(direction)
            else:raise RuntimeError('WLAN root direction boundary not reached')
            walks[direction]=states
        missing={'添加网络','WLAN 偏好设置','已保存的网络','Xiaomi_0421'}-reached
        if missing:raise RuntimeError('Post-boot WLAN root controls not reached: '+repr(missing))
        result['postboot_navigation']['wlan_direction_walks']=walks
        for _ in range(12):
            _,root,node,state=a.snap('final-reboot-wlan-toolbar-left')
            if not in_toolbar(root,node):raise RuntimeError('WLAN toolbar left traversal left its container')
            a.key('l');after=a.snap('final-reboot-wlan-toolbar-left-result')[3]
            if after['focus_signature']==state['focus_signature']:break
        else:raise RuntimeError('WLAN toolbar left boundary not reached')
        result['postboot_navigation']['wlan_toolbar']=[]
        for _ in range(12):
            _,root,node,state=a.snap('final-reboot-wlan-toolbar')
            if not in_toolbar(root,node):raise RuntimeError('WLAN toolbar traversal left its container')
            result['postboot_navigation']['wlan_toolbar'].append(state)
            a.key('r');after=a.snap('final-reboot-wlan-toolbar-right')[3]
            if after['focus_signature']==state['focus_signature']:break
        else:raise RuntimeError('WLAN toolbar boundary not reached')
        a.key('b');returned=a.snap('final-reboot-wlan-b-return',True)[3]
        if returned['package']!='com.android.settings' or returned['window']!='网络和互联网':
            raise RuntimeError('Post-boot WLAN B did not return to network settings')
        result['postboot_navigation']['b_return']=returned
        post_logs=read_ready('logcat -d -b all --pid='+pid)
        result['post_navigation_gpu_errors']=[line for line in post_logs.splitlines()
            if 'Aborting GPU composition' in line or 'Failed to bind framebuffer' in line
            or 'Crop rectangle dimensions not equal' in line]
        if result['post_navigation_gpu_errors']:
            raise RuntimeError('GPU errors during post-boot controller navigation')
        result['status']='PASS_CONTROLLER_RESTART_A_UNLOCK_TWELVE_COMPONENTS_SERVICES_GUARDS'
    except Exception as error:result.update(status='ERROR',error=repr(error));raise
    finally:
        try:
            if a and stay is not None:
                a.command('settings put global stay_on_while_plugged_in '+stay)
                result['stay_after']=read_ready('settings get global stay_on_while_plugged_in').strip()
                if result['stay_after']!=stay:
                    result['status']='CLEANUP_FAILED'
                    raise RuntimeError('Stay-awake setting not restored')
        except Exception as error:
            result.update(status='CLEANUP_FAILED',cleanup_error=repr(error));raise
        finally:
            if a:a.close()
            target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(result['status'],target,flush=True)


if __name__=='__main__':main()
