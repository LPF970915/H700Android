"""Fault-inject a missing search target, then restore its exact enabled state."""
import json
import re
import time
import uuid
from audit import Audit, OUT, adb
from explore import page_key
from followup import enter

PACKAGE='com.android.settings.intelligence'


def main():
    a=Audit(); result={}; restore=None
    output=OUT/'missing-activity-native-check.json'
    try:
        state=adb('dumpsys package '+PACKAGE)
        match=re.search(r'User 0: [^\n]*\benabled=(\d+)',state)
        if not match or match[1] not in ('0','1'):
            raise RuntimeError('Search must initially be enabled or in its default state')
        result['original_enabled_state']=int(match[1])
        enter(a,['网络和互联网','VPN'])
        a.key('r')
        _,root,focus,before=a.snap('missing-search-before',True)
        if not focus or before['focus']!='搜索设置': raise RuntimeError('Search was not selected')
        origin=page_key(root,before)
        pid=adb('pidof com.android.settings').strip()
        marker='missing-search-'+uuid.uuid4().hex[:12]
        a.command('log -t RGSPNavAudit '+marker)
        restore=('pm default-state --user 0 ' if match[1]=='0' else 'pm enable --user 0 ')+PACKAGE
        # Set restoration first: a command timeout must not leave the component disabled.
        a.command('pm disable-user --user 0 '+PACKAGE)
        a.key('a'); time.sleep(1)
        _,root,_,after=a.snap('missing-search-handled',True)
        result['before']=before;result['after']=after
        result['same_process']=adb('pidof com.android.settings').strip()==pid
        log=adb('logcat -d -t 800 -s RGSPNavAudit:I Settings:W AndroidRuntime:E')
        result['guard_log']=log.split(marker,1)[-1]
        if not result['same_process'] or page_key(root,after)!=origin:
            raise RuntimeError('Settings did not preserve its current page/process')
        if 'Unavailable settings activity on RGSP' not in result['guard_log']:
            raise RuntimeError('The generic ActivityNotFound handler was not exercised')
        if 'FATAL EXCEPTION' in result['guard_log']:
            raise RuntimeError('A fatal exception occurred during fault injection')
        result['status']='MISSING_TARGET_HANDLED_WITHOUT_EXIT'
    except Exception as error:
        result['status']='FAILED'; result['error']=repr(error)
        raise
    finally:
        try:
            if restore:
                result['restore_uart']=a.command(restore)
                state=adb('dumpsys package '+PACKAGE)
                match=re.search(r'User 0: [^\n]*\benabled=(\d+)',state)
                result['restored_enabled_state']=int(match[1]) if match else None
                if result['restored_enabled_state']!=result['original_enabled_state']:
                    result['status']='RESTORATION_FAILED'
                    raise RuntimeError('Search enabled state was not restored')
        finally:
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            a.close()
    print(result['status'],flush=True)


if __name__=='__main__': main()
