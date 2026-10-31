#!/usr/bin/env python3
"""Read-only, exact-card acceptance of Test1 boot/defaults/installed ABI.

Default is a plan. Raw observations are private; this does not drive keys,
install apps, reboot, format, or infer acceptance from a different system.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/dualabi-test1-20261031'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--phase',choices=['firstboot','reboot1','reboot2','coldboot'],default='firstboot')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN: exact USB/spare CID/Test1 marker; boot/setup complete; four APK SHA/ABI; '
              'Nav9, Home/accessibility, runtime properties, real zygote/core ELF classes; private logs. No device access.')
        return
    serial=json.loads((ROOT/'LOCAL_PRESERVE_H700_BASELINE_20261028/device-session.private.json').read_text(encoding='utf-8'))['serial']
    cid=json.loads((ROOT/'out/dualabi-prototype-image-20261031/card-before.private.json').read_text(encoding='utf-8'))['cid']
    adb=str(Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/platform-tools/adb.exe')
    if subprocess.check_output([adb,'-d','get-serialno'],timeout=10).decode().strip()!=serial:
        raise ValueError('Wrong USB device')
    raw={}
    def query(name,command,timeout=20):
        try:
            p=subprocess.run([adb,'-s',serial,'shell','-T',command],capture_output=True,timeout=timeout)
            value={'rc':p.returncode,'stdout':p.stdout.decode(errors='replace').replace('\r',''),
                   'stderr':p.stderr.decode(errors='replace')}
        except subprocess.TimeoutExpired as error:
            value={'rc':'timeout','stdout':(error.stdout or b'').decode(errors='replace'),
                   'stderr':(error.stderr or b'').decode(errors='replace')}
        raw[name]=value
        return value['stdout']
    def save():
        directory=OUT/'boot-observations';directory.mkdir(exist_ok=True)
        (directory/(args.phase+'-'+time.strftime('%Y%m%d-%H%M%S')+'.private.json')).write_text(json.dumps(raw,indent=2),encoding='utf-8')
    identity=query('identity','getprop ro.serialno; cat /sys/block/mmcblk0/device/cid; '
                   'getprop ro.product.device; getprop persist.vendor.rgsp.input_profile; '
                   'getprop ro.h700.prototype.image; id -u')
    if identity.splitlines()!=[serial,cid,'rgsp','rg34xxsp','dualabi-test1-20261031','0']:
        save();raise ValueError('Wrong boot/card/profile/Test1 marker')
    state=query('state','cat /proc/sys/kernel/random/boot_id; getprop sys.boot_completed; '
                'getprop ro.vndk.version; getprop dalvik.vm.heapgrowthlimit; getprop dalvik.vm.heapsize; '
                'getprop persist.vendor.hwc.software_vsync; cat /data/local/h700-prototype/complete')
    if state.splitlines()[1:]!=['1','29','128m','256m','true','TEST1_APPS_AND_DEFAULTS_INSTALLED']:
        query('setup-log','cat /data/local/h700-prototype/setup.log; getprop sys.h700.prototype.setup')
        save();print('TEST1_BOOT_OR_INSTALL_NOT_READY; private observation retained');raise SystemExit(2)
    image=json.loads((OUT/'image-lock.json').read_text(encoding='utf-8'))
    parent=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/overlay-lock.json').read_text())
    listing=query('apps-list','cat /system/etc/h700-prototype/apps.list')
    if hashlib.sha256(listing.encode()).hexdigest()!=parent['system']['/system/etc/h700-prototype/apps.list']['sha256']:
        save();raise ValueError('Prototype APK inventory changed')
    apps=[]
    for line in listing.splitlines():
        package,filename,abi,digest=line.split()
        installed=query(package+'-path','pm path '+shlex.quote(package)).strip()
        if not installed.startswith('package:/data/app/') or '\n' in installed:
            save();raise ValueError('Test APK is not the expected fresh standalone install')
        path=installed[len('package:'):]
        value=query(package,'sha256sum '+shlex.quote(path)+'; dumpsys package '+shlex.quote(package)+' | grep primaryCpuAbi=')
        if value.split()[0]!=digest or 'primaryCpuAbi='+abi not in value:
            save();raise ValueError('Installed APK digest/ABI mismatch')
        apps.append({'package':package,'abi':abi,'sha256':digest})
    nav=query('navigation','pm path com.roc.rgsp.navtrial; dumpsys package com.roc.rgsp.navtrial | grep versionName; '
              'sha256sum /system/app/RGSPNavigation/RGSPNavigation.apk')
    if not nav.startswith('package:/system/app/RGSPNavigation/RGSPNavigation.apk\n'):
        save();raise ValueError('Runtime navigation update present; not the unmodified Test1 runtime')
    if 'versionName=1.6-prototype-a-unlock' not in nav or image['modified_files']['/system/app/RGSPNavigation/RGSPNavigation.apk']['sha256'] not in nav:
        save();raise ValueError('Navigation9 mismatch')
    defaults=query('defaults','cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME; '
                   'settings get global device_provisioned; settings get secure user_setup_complete; '
                   'settings get secure accessibility_enabled; settings get secure enabled_accessibility_services; '
                   'settings get global bluetooth_on; stat -c "%Y" /data/local/h700-prototype/complete; '
                   'cat /storage/emulated/0/Android/data/com.retroarch.ra32/files/retroarch.cfg')
    if 'com.overdevs.at4k/.MainActivity' not in defaults or 'com.roc.rgsp.navtrial/.NavigationService' not in defaults:
        save();raise ValueError('Home/navigation defaults missing')
    if 'joypad_autoconfig_dir = "/data/user/0/com.retroarch.ra32/autoconfig"' not in defaults or 'menu_swap_ok_cancel_buttons = "false"' not in defaults:
        save();raise ValueError('Fresh RA configuration missing')
    provisioning=query('provisioning','settings get global device_provisioned; settings get secure user_setup_complete; '
                       'settings get secure accessibility_enabled; settings get global bluetooth_on')
    if provisioning.splitlines()!=['1','1','1','0']:
        save();raise ValueError('Provisioning/radio defaults mismatch')
    bits={}
    for name,expected in [('zygote64',64),('zygote',32),('system_server',64),('surfaceflinger',64)]:
        value=query(name,'p=$(pidof '+name+'); echo PID=$p; od -An -t u1 -N5 /proc/$p/exe')
        lines=value.splitlines()
        if len(lines)!=2 or lines[1].split()!=['127','69','76','70',str(expected//32)]:
            save();raise ValueError('Real core ELF class mismatch')
        bits[name]=expected
    growth=query('grow-and-mounts','cat /data/.rgsp-capacity-v1; '
          'if [ -e /data/.rgsp-fat-grow-pending-v1 ]; then echo FAT_PENDING; else echo FAT_NOT_PENDING; fi; '
          'cat /sys/block/mmcblk0/mmcblk0p7/start /sys/block/mmcblk0/mmcblk0p7/size '
          '/sys/block/mmcblk0/mmcblk0p8/start /sys/block/mmcblk0/mmcblk0p8/size; cat /proc/mounts')
    if '244277248' not in growth or 'FAT_NOT_PENDING' not in growth or '/dev/mmcblk0p5 / ext4 ro,' not in growth:
        save();raise ValueError('Capacity/grow/read-only root checks incomplete')
    query('setup-log','cat /data/local/h700-prototype/setup.log')
    query('crash','logcat -b crash -d -v brief')
    if query('boot-after','cat /proc/sys/kernel/random/boot_id').strip()!=state.splitlines()[0]:
        save();raise ValueError('Boot changed during observation')
    save()
    result={'phase':args.phase,'image_sha256':image['sha256'],'exact_spare_guard_pass':True,
            'boot_and_fresh_installer_complete':True,'installed_apks':apps,'actual_core_elf_bits':bits,
            'home_and_navigation_defaults':True,'capacity_and_read_only_root_checked':True,
            'physical_A_unlock_checked_by_this_read_only_audit':False,
            'app_rendering_performance_or_full_hardware_acceptance':False}
    (OUT/(args.phase+'-device-pass.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('TEST1_'+args.phase.upper()+'_BOOT_INSTALL_ABI_AND_DEFAULTS_PASS')


if __name__=='__main__':main()
