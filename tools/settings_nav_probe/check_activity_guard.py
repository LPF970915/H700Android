"""Exercise the actual Bluetooth controller's missing-target path with a temporary handler."""
import json
import subprocess
import time
import uuid
from audit import Audit, OUT, adb, ADB, TARGET
from explore import page_key
from followup import enter

PACKAGE='com.roc.rgsp.audit.missingtarget'


def installed():
    return 'package:'+PACKAGE in adb('pm list packages '+PACKAGE).splitlines()


def main():
    a=Audit(); result={}; created=False
    try:
        if installed(): raise RuntimeError('The reserved test package already exists; no changes made')
        apk=OUT/'fault-target/FaultTarget.apk'
        if not apk.is_file(): raise RuntimeError('Build the temporary manifest-only receiver first')
        created=True
        subprocess.run([ADB,'-s',TARGET,'install','--no-incremental',str(apk)],check=True,capture_output=True,timeout=40)
        enter(a,['已连接的设备','连接偏好设置'])
        a.seek('通过蓝牙收到的文件')
        _,root,focus,before=a.snap('bt-fault-before',True)
        if not focus or before['focus']!='通过蓝牙收到的文件': raise RuntimeError('The test entry was not selected')
        origin=page_key(root,before)
        pid=adb('pidof com.android.settings').strip()
        marker='bt-missing-target-'+uuid.uuid4().hex[:12]
        a.command('log -t RGSPNavAudit '+marker)
        a.command('pm disable-user --user 0 '+PACKAGE)
        _,root,focus,disabled=a.snap('bt-fault-target-disabled')
        result['before']=before; result['target_disabled']=disabled
        if disabled['focus']!='通过蓝牙收到的文件' or not focus.get('enabled'):
            result['status']='UNAVAILABLE_ENTRY_REMOVED_BEFORE_LAUNCH'
        else:
            a.key('a'); time.sleep(1)
            _,root,_,after=a.snap('bt-fault-handled',True)
            result['after']=after
            result['same_process']=adb('pidof com.android.settings').strip()==pid
            log=adb('logcat -d -t 1000 -s RGSPNavAudit:I Settings:W AndroidRuntime:E')
            result['guard_log']=log.split(marker,1)[-1]
            if not result['same_process'] or page_key(root,after)!=origin:
                raise RuntimeError('Settings did not preserve its page/process')
            if 'Unavailable settings activity on RGSP' not in result['guard_log']:
                raise RuntimeError('The generic ActivityNotFound handler was not exercised')
            if 'FATAL EXCEPTION' in result['guard_log']:
                raise RuntimeError('A fatal exception occurred during fault injection')
            result['status']='MISSING_TARGET_HANDLED_WITHOUT_EXIT'
    except Exception as error:
        result['status']='FAILED';result['error']=repr(error)
        raise
    finally:
        try:
            if created:
                if installed(): result['cleanup_uart']=a.command('pm uninstall '+PACKAGE)
                result['test_package_removed']=not installed()
                if not result['test_package_removed']:
                    result['status']='CLEANUP_FAILED'
                    raise RuntimeError('The temporary test package was not removed')
        finally:
            (OUT/'bt-missing-activity-native-check.json').write_text(
                json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            a.close()
    print(result['status'],flush=True)


if __name__=='__main__':main()
