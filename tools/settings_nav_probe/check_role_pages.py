"""Test default-app role pages after the TV/handheld theme mismatch repair."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from audit import Audit, OUT, adb, descendants
from files import focus
from followup import top
from explore import Explorer, new_ui_crash
from graph import graph


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True)
    p.add_argument('--resume',type=Path);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('role-pages-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    query='cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME'
    a=Audit();result={'status':'RUNNING','new_default_app_selected':False,
                     'setup_scope':'App-info/role-list intent launches are setup only; actual default-home shortcut, rows, directions and B are controller input.'}
    try:
        result['home_before']=adb(query)
        if 'com.overdevs.at4k/.MainActivity' not in result['home_before']:raise RuntimeError('Unexpected default HOME; preserved')
        crash=adb('logcat -d -b crash -v threadtime')
        if args.resume:
            previous=json.loads(args.resume.read_text(encoding='utf8'))
            if (previous.get('home_graph')!='REACHABLE_FOCUS_GRAPH_SCANNED'
                    or previous.get('existing_holder_a',{}).get('package')!='com.overdevs.at4k'
                    or previous.get('home_before')!=result['home_before']):
                raise RuntimeError('Resume receipt does not prove the original graph and expected HOME A')
            result['original_graph_and_a']={'source':str(args.resume),'sha256':hashlib.sha256(args.resume.read_bytes()).hexdigest(),
                                            'graph':previous['home_graph'],'existing_holder_a':previous['existing_holder_a'],
                                            'scope':'HomeRoleBehavior.onHolderSelectedAsUser intentionally launches HOME; prior return assertion was incorrect'}
        a.command('am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:com.overdevs.at4k')
        result['app_info']=a.snap('role-fix-parent-app-info',True)[3]
        top(a)
        try:a.seek('主屏幕应用',limit=30,actionable=True)
        except RuntimeError:
            top(a);a.seek('高级',actionable=True);a.key('a');a.seek('主屏幕应用',actionable=True)
        result['shortcut_focus']=a.snap('role-fix-home-shortcut-focus',True)[3];a.key('a')
        for _ in range(12):
            _,root,_,state=a.snap('role-fix-default-home-entry',True)
            if state['package']=='com.android.permissioncontroller':break
            time.sleep(.2)
        else:raise RuntimeError('Default HOME role page did not open')
        result['role_entry']=state
        if not any(n.get('visible') and n.get('id','').endswith('/action_bar') for n in descendants(root)):
            raise RuntimeError('TV role page has no native ActionBar')
        after_crash=adb('logcat -d -b crash -v threadtime')
        if new_ui_crash(crash,after_crash):raise RuntimeError('Default HOME role page crashed')
        if not args.resume:
            value=graph(a,['默认应用主题修复',args.tag,'主屏幕应用'],220)
            result['home_graph']=value['status']
            if value['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Default HOME graph incomplete')
        else:result['home_graph']=previous['home_graph']
        # B is tested separately from HomeRoleBehavior's intentional HOME launch.
        state=a.snap('role-fix-before-return')[3]
        if state['package']=='com.android.permissioncontroller':a.key('b')
        result['home_return']=a.snap('role-fix-default-home-b-return',True)[3]
        if result['home_return']['package']!='com.android.settings' or result['home_return']['window']!='应用信息':
            raise RuntimeError('Default HOME did not return to app info')
        a.command('am start -a android.settings.MANAGE_DEFAULT_APPS_SETTINGS')
        for _ in range(12):
            _,root,_,state=a.snap('role-fix-default-list-entry',True)
            if state['package']=='com.android.permissioncontroller':break
            time.sleep(.2)
        else:raise RuntimeError('Default app list did not open')
        result['list_entry']=state
        e=Explorer(a,args.tag+'-default-role-list')
        if e.output.exists():raise ValueError('Fresh role-list scan required')
        e.visit(['设置','应用和通知','默认应用',args.tag])
        result['default_list_scan']=e.output.name
        if e.pages[0]['status']!='BIDIRECTIONAL_SCAN_DONE':raise RuntimeError('Default app list scan not complete')
        result['home_after']=adb(query)
        if result['home_after']!=result['home_before']:raise RuntimeError('Default HOME changed')
        result['permissioncontroller_sha256']=adb('sha256sum '+adb('pm path com.android.permissioncontroller').strip().removeprefix('package:')).split()[0]
        result['status']='PASS_TV_ROLE_ACTIONBAR_HOME_SHORTCUT_GRAPH_DEFAULT_LIST_CHILDREN_RETURN_NO_DEFAULT_CHANGE'
    except Exception as error:result.update(status='ERROR',error=repr(error));raise
    finally:
        a.close();output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(result['status'],flush=True)


if __name__=='__main__':main()
