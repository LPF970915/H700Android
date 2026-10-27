"""Disable developer options, re-enable with seven real Build-number presses, then enable USB debugging."""
import json,time
from audit import Audit,OUT,adb,descendants,label
from followup import enter,top

def flags(a):
    return a.command('echo DEV=$(settings get global development_settings_enabled); echo ADB=$(settings get global adb_enabled); echo DAEMON=$(getprop init.svc.adbd)')

def main():
    a=Audit();r={'status':'RUNNING'};started=False
    try:
        r['baseline']=adb('settings list global');r['baseline_flags']=flags(a)
        if 'DEV=1' not in r['baseline_flags'] or 'ADB=1' not in r['baseline_flags']:raise RuntimeError('Expected enabled developer/debug baseline')
        enter(a,['系统','开发者选项']);top(a);a.key('d');_,root,focus,r['before']=a.snap('dev-first-before',True)
        master=next(n for n in descendants(root) if n.get('id','').endswith('/switch_bar'))
        owned={n.get('id') for n in descendants(master)}
        if focus.get('id') not in owned:raise RuntimeError('Developer master switch is not focused')
        a.observation_transport='uart';started=True;a.key('a');r['disabled']=a.snap('dev-first-disabled',True)[3];r['disabled_flags']=flags(a)
        if 'DEV=0' not in r['disabled_flags'] or 'ADB=0' not in r['disabled_flags'] or 'DAEMON=stopped' not in r['disabled_flags']:raise RuntimeError('Developer switch failed to naturally disable debugging')
        a.key('b');r['system']=a.snap('dev-first-back-system')[3]
        a.key('b');_,root,_,r['home']=a.snap('dev-first-back-home')
        if not any(n.get('id','').endswith('/search_action_bar') for n in descendants(root)):raise RuntimeError('Homepage not reached while ADB stopped')
        top(a);a.seek('关于手机',actionable=True);a.key('a');top(a);a.seek('版本号',actionable=True)
        r['build_presses']=[]
        for i in range(7):
            _,_,focus,state=a.snap('dev-build-'+str(i+1))
            if not focus or label(focus)!='版本号':raise RuntimeError('Build-number focus lost')
            a.key('a');r['build_presses'].append(state)
        r['after_seven_flags']=flags(a)
        if 'DEV=1' not in r['after_seven_flags'] or 'ADB=0' not in r['after_seven_flags']:raise RuntimeError('Seven presses did not enable developer options with USB debugging still off')
        enter(a,['系统','开发者选项']);a.seek('USB 调试',actionable=True);r['usb_off']=a.snap('dev-usb-off',True)[3];a.key('a')
        _,root,_,r['usb_dialog']=a.snap('dev-usb-enable-dialog',True)
        text=' '.join(n.get('text','') for n in descendants(root))
        if 'USB' not in text or '调试' not in text or not any(n.get('id')=='android:id/button1' for n in descendants(root)):raise RuntimeError('Wrong USB debug confirmation')
        for _ in range(6):
            _,_,focus,state=a.snap('dev-usb-positive')
            if focus and focus.get('id')=='android:id/button1':r['usb_positive']=state;break
            a.key('r')
        else:raise RuntimeError('Positive debug confirmation unreachable')
        a.key('a');r['enabled_poll']=[]
        for _ in range(12):
            r['enabled_flags']=flags(a);r['enabled_poll'].append(r['enabled_flags'])
            if 'DEV=1' in r['enabled_flags'] and 'ADB=1' in r['enabled_flags'] and 'DAEMON=running' in r['enabled_flags']:break
            time.sleep(.5)
        else:raise RuntimeError('Explicit confirmation failed to enable debugging after settling')
        r['guard_restore']=a.command('if [ -f /system/bin/rgsp-wifi-adb-session.sh ]; then sh /system/bin/rgsp-wifi-adb-session.sh; else sh /data/local/tmp/rgsp-restore-debug.sh; fi')
        a.observation_transport='adb';r['after']=a.snap('dev-first-finished',True)[3]
        r['after_global']=adb('settings list global')
        def mapping(text):return dict(line.split('=',1) for line in text.splitlines() if '=' in line)
        before=mapping(r['baseline']);after=mapping(r['after_global']);r['global_changes']={k:{'before':before.get(k),'after':after.get(k)} for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
        # The test legitimately resets debug preferences. Preserve the initial
        # plugged-in screen-awake setting, which is independent of navigation.
        if 'stay_on_while_plugged_in' in r['global_changes'] and before.get('stay_on_while_plugged_in','').isdigit():
            a.command('settings put global stay_on_while_plugged_in '+before['stay_on_while_plugged_in']);r['awake_restored']=True
        r['status']='PASS_SEVEN_BUILD_PRESSES_AND_EXPLICIT_USB_DEBUG_CONFIRMATION';print(r['status'],flush=True)
    except Exception as e:
        r['status']='ERROR';r['error']=repr(e)
        if started:
            r['recovery_uart']=a.command('settings put global development_settings_enabled 1; settings put global adb_enabled 1; if [ -f /system/bin/rgsp-wifi-adb-session.sh ]; then sh /system/bin/rgsp-wifi-adb-session.sh; else sh /data/local/tmp/rgsp-restore-debug.sh; fi')
        raise
    finally:a.close();(OUT/'developer-first-enable-20261024.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
