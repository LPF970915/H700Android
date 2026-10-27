"""Require a real service-detail transition, rather than relabeling its list."""
import argparse
import json
import time
from audit import Audit, OUT, adb, descendants
from followup import top
from files import focus
from explore import Explorer


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--repeat',type=int,default=1);args=p.parse_args()
    if not 1<=args.repeat<=5:raise ValueError('One to five guarded entry trials are supported')
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('running-service-detail-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    a=Audit();r={'status':'RUNNING','stop_or_report_confirmed':False}
    query='dumpsys activity service com.roc.rgsp.navtrial/.NavigationService'
    try:
        r['pid_before']=adb('pidof com.roc.rgsp.navtrial').strip()
        package_path=adb('pm path com.roc.rgsp.navtrial').strip().removeprefix('package:')
        r['navigation_apk_sha256']=adb('sha256sum '+package_path).split()[0]
        a.command('am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS')
        top(a);a.seek('正在运行的服务',actionable=True);a.key('a')
        for _ in range(12):
            _,root,_,s=a.snap('running-detail-list-ready')
            if s['window']=='正在运行的服务' and any(n.get('id','').endswith('/listHeader') for n in descendants(root)):break
            time.sleep(.3)
        else:raise RuntimeError('Expected running-service list not ready')
        r['list_entry']=s
        # The target starts below the tall memory header on this LCD; list
        # readiness must not require an off-screen, recycled row to be present.
        a.seek('RGSP D-pad Navigation',actionable=True)
        _,root,node,r['row_focus']=a.snap('running-detail-exact-row',True)
        if not node or not node.get('enabled') or not node.get('clickable'):raise RuntimeError('Service row not actionable')
        r['row_node']=node;r['navigation_before']=adb(query)
        a.key('a');r['transition_observations']=[]
        for _ in range(10):
            _,root,_,s=a.snap('running-detail-after-a',True);r['transition_observations'].append(s)
            if s['window']=='正在运行的应用' and any(n.get('visible') and n.get('id')=='com.android.settings:id/left_button' for n in descendants(root)):break
            time.sleep(.3)
        else:
            r['navigation_after']=adb(query)
            raise RuntimeError('Actual A did not enter running-app details; no second A or Stop injected')
        r['detail_entry']=s
        e=Explorer(a,'running-detail-confirmed@'+args.tag)
        if e.output.exists():raise ValueError('Fresh service-detail scan required')
        e.visit(['设置','系统','开发者选项','正在运行的服务','RGSP D-pad Navigation'])
        if e.pages[0]['status']!='BIDIRECTIONAL_SCAN_DONE':raise RuntimeError('Confirmed detail scan incomplete')
        r['detail_scan']=e.output.name
        a.key('b');r['returned']=a.snap('running-detail-b-return',True)[3]
        if r['returned']['window']!='正在运行的服务' or r['returned']['window_id']!=r['list_entry']['window_id']:
            raise RuntimeError('Service detail B did not return to original list')
        r['additional_immediate_a_trials']=[]
        for trial in range(1,args.repeat):
            a.seek('RGSP D-pad Navigation',actionable=True)
            # No extra device RPC between the seek snapshot and A: exercise the
            # live updating row with the same immediate timing as the old miss.
            before=json.loads((OUT/'states.jsonl').read_text(encoding='utf8').splitlines()[-1])
            if not str(before.get('focus','')).startswith('RGSP D-pad Navigation'):
                raise RuntimeError('Unexpected target before repeated guarded A')
            a.key('a')
            for _ in range(10):
                _,root,_,opened=a.snap('running-detail-repeat-'+str(trial),True)
                if opened['window']=='正在运行的应用' and any(n.get('visible') and n.get('id')=='com.android.settings:id/left_button' for n in descendants(root)):break
                time.sleep(.2)
            else:raise RuntimeError('Immediate A trial did not open confirmed details')
            a.key('b');returned=a.snap('running-detail-repeat-b-'+str(trial),True)[3]
            if returned['window_id']!=r['list_entry']['window_id']:raise RuntimeError('Repeated service detail B lost its parent')
            r['additional_immediate_a_trials'].append({'before':before,'opened':opened,'returned':returned})
        r['pid_after']=adb('pidof com.roc.rgsp.navtrial').strip()
        if r['pid_after']!=r['pid_before']:raise RuntimeError('Navigation service process changed')
        r['status']='PASS_ACTUAL_A_RUNNING_APP_DETAILS_BUTTON_FOCUS_B_NO_STOP'
    except Exception as error:r.update(status='ERROR',error=repr(error));raise
    finally:a.close();output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    print(r['status'],flush=True)


if __name__=='__main__':main()
