"""Guarded live allocator reserve trial; two real kernel reboots and HAT stress."""
import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from audit import Audit, OUT, ROOT, adb
from explore import Explorer

BEFORE='d873a1cb5e0b8b2357cf826adeca5c76bba17d4999dd1ec270547d6e23dca849'
AFTER='7f26f9a5e021001028e94315aa4996671b657cabc4e2a30829c1fc2030ec39ea'
STAGE='/data/local/tmp/rgsp-startup-buffer-reserve-20261026'
TARGET='/system/lib/libsurfaceflinger.so'
OUTPUT=ROOT/'out/flicker-investigation-20261026/startup-buffer-reserve'


def read_ready(command):
    # Only read-only observations may be retried after a transport interruption.
    last=None
    for _ in range(8):
        try:return adb(command)
        except (subprocess.SubprocessError,RuntimeError) as error:
            last=error;time.sleep(2)
    raise last


def stop_probe(a):
    a.command('touch /data/local/tmp/nav-passive-audit/stop')
    for _ in range(40):
        status=read_ready("ps -A -o PID,ARGS | grep 'app_process /system/bin Dump --daemon' | grep -v grep || true")
        if not status.strip():return
        time.sleep(.3)
    raise RuntimeError('Owned passive probe did not exit')


def ready(a, tag):
    read_ready('getprop ro.serialno')
    a.command('svc power stayon true')
    # This is graphics-test setup, never counted as controller unlock evidence.
    a.command('input keyevent 224; wm dismiss-keyguard')
    a.ensure_probe()
    a.key('home')
    for _ in range(12):
        state=a.snap(tag)[3]
        if state['package']=='com.overdevs.at4k':return state
        time.sleep(.5)
    raise RuntimeError('Graphics setup did not reach the known launcher')


def switch(a, mode):
    stop_probe(a)
    a.command('nohup sh '+STAGE+'/trial.sh '+mode+' > '+STAGE+'/'+mode+'-v2.log 2>&1 < /dev/null & true')
    for _ in range(50):
        output=a.command('tail -n 5 '+STAGE+'/'+mode+'-v2.log')
        if 'SF_'+mode+'=STABLE' in output:return output
        if 'ROLLED_BACK' in output or 'TIMEOUT' in output or 'REPLACEMENT_FAILED' in output:
            raise RuntimeError('Module switch failed: '+output)
        time.sleep(4)
    raise RuntimeError('Module switch did not finish')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:parser.error('--execute required')
    receipt=OUTPUT/('live-two-boot-v2-'+datetime.datetime.now().strftime('%H%M%S')+'.json')
    result={'status':'STARTING','physical_power_cycle':False,'cold_boots':[],
            'setup_only':['temporary stay awake','wm dismiss-keyguard'],
            'old_failed_receipt':'live-two-boot-validation.json'}
    a=Audit();keep=False;stay=None
    def save():receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    try:
        stay=read_ready('settings get global stay_on_while_plugged_in').strip()
        result['stay_before']=stay
        if stay not in ('0','1','2','3','4','5','6','7'):raise RuntimeError('Unknown stay-awake baseline')
        if read_ready('sha256sum '+TARGET).split()[0]!=BEFORE:raise RuntimeError('Unexpected baseline module')
        result['setup']=ready(a,'reserve-v2-preflight')
        result['install_log']=switch(a,'install');save()
        ready(a,'reserve-v2-installed')
        for index in (1,2):
            stop_probe(a);a.close();a=None
            print('RESERVE_V2_KERNEL_REBOOT',index,flush=True)
            subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name('reboot_check.py')),'--execute'],check=True)
            a=Audit()
            # adbd can report device before its first shell stream is ready.
            read_ready('getprop ro.serialno')
            result['last_setup']=ready(a,'reserve-v2-boot'+str(index))
            sf=read_ready('dumpsys SurfaceFlinger')
            (OUTPUT/('v2-boot'+str(index)+'-surfaceflinger.txt')).write_text(sf,encoding='utf8')
            lines=[line for line in sf.splitlines() if 'RGSP startup allocator reserve' in line]
            if not lines:raise RuntimeError('Startup reserve not active')
            sha=read_ready('sha256sum '+TARGET).split()[0]
            if sha!=AFTER:raise RuntimeError('Candidate module did not persist')
            Explorer(a).goto_root()
            entry=a.snap('reserve-v2-settings-entry',True)[3]
            if entry['package']!='com.android.settings':raise RuntimeError('Settings entry failed')
            for key in ['d']*22+['u']*22+['r','l']*8:a.key(key)
            end=a.snap('reserve-v2-hat-end',True)[3]
            pid=read_ready('pidof surfaceflinger').strip()
            logs=read_ready('logcat -d -b all --pid='+pid)
            bad=[line for line in logs.splitlines() if 'Crop rectangle dimensions not equal' in line
                 or 'Failed to bind framebuffer' in line or 'Aborting GPU composition' in line]
            (OUTPUT/('v2-boot'+str(index)+'-gpu-errors.log')).write_text('\n'.join(bad),encoding='utf8')
            boot={'index':index,'boot_id':read_ready('cat /proc/sys/kernel/random/boot_id').strip(),
                  'sf_pid':pid,'library_sha256':sha,'reserve_dump_lines':lines,'gpu_error_lines':bad,
                  'settings_entry':entry,'after_hat':end}
            result['cold_boots'].append(boot);save()
            print('RESERVE_V2_BOOT_RESULT',index,'GPU_ERRORS',len(bad),flush=True)
            if bad:raise RuntimeError('GPU composition failure with reserve')
            a.key('home')
        keep=True;result['status']='PASS_TWO_KERNEL_REBOOTS_RESERVE_ACTIVE_ZERO_GPU_IMPORT_ERRORS'
    except Exception as error:
        result['error']=repr(error)
        result['status']='FAILED_PENDING_ROLLBACK'
        raise
    finally:
        try:
            if a is None:a=Audit()
            if not keep and read_ready('sha256sum '+TARGET).split()[0]==AFTER:
                result['rollback_log']=switch(a,'rollback')
                result['status']='FAILED_ORIGINAL_RESTORED'
            result['cleanup_home']=ready(a,'reserve-v2-cleanup-home')
            if stay is not None:a.command('settings put global stay_on_while_plugged_in '+stay)
            result['final_sha256']=read_ready('sha256sum '+TARGET).split()[0]
            result['system_mount']=read_ready("grep '^/dev/mmcblk0p5 / ' /proc/mounts")
            result['stay_restored']=read_ready('settings get global stay_on_while_plugged_in').strip()
        finally:
            if a:a.close()
            save();print('RESERVE_RECEIPT',receipt,flush=True)


if __name__=='__main__':main()
