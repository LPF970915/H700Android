"""Exercise only our navigation service before binding and through process death."""
import argparse
import json
import re
import shlex
import time
from audit import Audit, OUT, adb

PKG='com.roc.rgsp.navtrial'
COMPONENT=PKG+'/.NavigationService'


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true')
    p.add_argument('--tag',required=True);p.add_argument('--expected-nav-sha',required=True)
    p.add_argument('--expected-services-sha',required=True);args=p.parse_args()
    if not args.execute:p.error('--execute required; temporarily unbinds only our own navigation service')
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('accessibility-lifecycle-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    a=Audit();r={'status':'RUNNING'};before=None;master=None
    query='dumpsys activity service '+COMPONENT
    def bound():
        for _ in range(50):
            state=adb(query)
            if 'navigationVersion=35 mode=' in state and re.search(r'flags=114\b',state):return state
            time.sleep(.3)
        raise RuntimeError('Own navigation service did not rebind')
    def same_server():
        current=adb('pidof system_server').strip()
        if current!=r['system_server_before']:raise RuntimeError('System server changed during lifecycle test')
    def stop_own_service():
        # Android10 am stopservice returns 1 when it succeeds and 255 when the
        # service is already absent. Accept only those explicit semantic replies.
        return a.command('stop_output="$(am stopservice -n '+COMPONENT+' 2>&1)"; '
            'printf "%s\\n" "$stop_output"; case "$stop_output" in '
            '*"Service stopped"*|*"Service not stopped: was not running."*) true;; *) false;; esac')
    try:
        path=adb('pm path '+PKG).strip().removeprefix('package:')
        if adb('sha256sum '+path).split()[0]!=args.expected_nav_sha:raise RuntimeError('Unexpected own service APK')
        if adb('sha256sum /system/framework/services.jar').split()[0]!=args.expected_services_sha:raise RuntimeError('Unexpected framework JAR')
        r['system_server_before']=adb('pidof system_server').strip();r['bound_before']=bound()
        before=adb('settings get secure enabled_accessibility_services').strip();master=adb('settings get secure accessibility_enabled').strip()
        entries=before.split(':');own=[x for x in entries if x in (COMPONENT,PKG+'/'+PKG+'.NavigationService')]
        if len(own)!=1 or master!='1':raise RuntimeError('Unexpected accessibility baseline; preserved')
        r['enabled_before']=before;r['master_before']=master
        remaining=':'.join(x for x in entries if x not in own)
        a.command('settings put secure enabled_accessibility_services '+shlex.quote(remaining))
        for _ in range(30):
            state=adb(query)
            if 'SERVICE '+COMPONENT not in state:break
            time.sleep(.2)
        else:raise RuntimeError('Own service did not unbind')
        a.command('am startservice -n '+COMPONENT)
        r['unbound_dump']=adb(query)
        if not re.search(r'flags=0\b',r['unbound_dump']):raise RuntimeError('Unbound dump did not exercise null-service-info branch')
        same_server();r['stop_unbound_service']=stop_own_service()
        a.command('settings put secure enabled_accessibility_services '+shlex.quote(before))
        a.command('settings put secure accessibility_enabled '+master)
        r['rebound_after_unbound_dump']=bound();same_server();r['death_trials']=[]
        for trial in range(2):
            pid=adb('pidof '+PKG).strip()
            if not re.fullmatch(r'[0-9]+',pid):raise RuntimeError('Ambiguous own process; no signal sent')
            a.command('kill -9 '+pid)
            state=bound();new=adb('pidof '+PKG).strip()
            if new==pid:raise RuntimeError('Own process did not restart after the controlled death')
            same_server();r['death_trials'].append({'old_pid':pid,'new_pid':new,'bound':state})
            print('OWN_SERVICE_DEATH_REBIND_PASS',trial+1,flush=True)
        r['status']='PASS_UNBOUND_NULL_SAFE_DUMP_TWO_OWN_SERVICE_DEATHS_CORE_STABLE'
    except Exception as error:r.update(status='ERROR',error=repr(error));raise
    finally:
        try:
            if before is not None and master is not None:
                try:r['stop_own_service_cleanup']=stop_own_service()
                finally:
                    try:a.command('settings put secure enabled_accessibility_services '+shlex.quote(before))
                    finally:a.command('settings put secure accessibility_enabled '+master)
                r['bound_after_cleanup']=bound()
                r['enabled_after']=adb('settings get secure enabled_accessibility_services').strip()
                r['master_after']=adb('settings get secure accessibility_enabled').strip()
                if r['enabled_after']!=before or r['master_after']!=master:raise RuntimeError('Accessibility baseline not restored')
        except Exception as error:r.update(status='CLEANUP_FAILED',cleanup_error=repr(error));raise
        finally:a.close();output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    print(r['status'],flush=True)


if __name__=='__main__':main()
