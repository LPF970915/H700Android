"""Revisit explicit audit gaps through Settings' real controller entry paths."""
import argparse
import datetime
import json
import re
import time
from pathlib import Path
from audit import Audit, OUT, viewport, descendants
from explore import Explorer, in_toolbar
from graph import graph

SETUP_PAGES={
    'android.settings.INPUT_METHOD_SETTINGS':(['系统','语言和输入法'],'语言和输入法'),
    'android.settings.APPLICATION_DEVELOPMENT_SETTINGS':(['系统','开发者选项'],'开发者选项'),
    'android.settings.WIFI_SETTINGS':(['网络和互联网','WLAN'],'WLAN'),
    'android.settings.WIRELESS_SETTINGS':(['网络和互联网'],'网络和互联网'),
}

def top(a):
    previous=None; repeated=0; toolbar_content_probe=False
    for _ in range(200):
        _,root,node,state=a.snap('followup-top')
        boundary=(state['focus_signature'],viewport(root))
        if boundary==previous: repeated+=1
        else: repeated=0
        if repeated>=2:
            if not toolbar_content_probe and in_toolbar(root,node):
                # A retained Activity can focus its toolbar while its list is
                # still scrolled. Enter that list once, then walk Up through
                # its real content before accepting the toolbar as top.
                toolbar_content_probe=True
                a.key('d'); previous=None; repeated=0
                continue
            return
        previous=boundary
        row=re.search(r'\brow=(\d+)',state.get('focus_signature') or '')
        if (a.observation_transport=='uart' or
                (state['package']=='com.android.settings' and state['window']=='开发者选项'
                 and row and int(row[1])>12)):
            # Up only traverses focus. Real held HAT repeats reach the same
            # clamped boundary while avoiding full UART dumps after every row.
            for _ in range(3):a.hold('u')
        else:a.key('u')
    raise RuntimeError('Could not reach top boundary')

def seek_component(a, component):
    if component.startswith('查看全部'):
        _, root, _, _ = a.snap('followup-app-header-button')
        if any(n.get('visible') and n.get('id')=='com.android.settings:id/header_details'
               for n in descendants(root)):
            from files import focus
            focus(a,'header_details',expected_package='com.android.settings')
            return
    _, root, _, state = a.snap('followup-visible-directional-target')
    if any(n.get('visible') and (n.get('text')==component or n.get('desc')==component)
           for n in descendants(root)):
        # Visible toolbar actions and grid cells require spatial traversal;
        # a vertical-only search can legitimately bypass their column.
        from files import focus
        focus(a,component,expected_package=state['package'])
        return
    a.seek(component,actionable=True)


def enter(a,path):
    Explorer(a).goto_root()
    for component in path:
        top(a)
        try: seek_component(a,component)
        except RuntimeError:
            top(a); a.seek('高级',actionable=True); a.key('a'); a.seek(component,actionable=True)
        a.key('a')


def enter_supplement(a,item):
    """Reuse audited parent entry coverage; optional intent is setup only."""
    action=item.get('setup_action')
    if not action:
        enter(a,item['path']);return
    prefix,title=SETUP_PAGES[action]
    if item['path'][:len(prefix)]!=prefix:
        raise ValueError('Setup intent does not match the canonical parent')
    # On this Android10 build INPUT_METHOD_SETTINGS resolves to "管理键盘",
    # not the language/input dashboard. Use its manifest-verified component.
    command=("am start -n 'com.android.settings/.Settings$LanguageAndInputSettingsActivity'"
             if action=='android.settings.INPUT_METHOD_SETTINGS' else 'am start -a '+action)
    item['resolved_setup_command']=command
    a.command(command)
    for _ in range(12):
        state=a.snap('supplement-parent-setup')[3]
        if state['package']=='com.android.settings' and state['window']==title:break
        time.sleep(.2)
    else:
        # Settings can deliver this intent to an existing alias Activity while
        # retaining its current fragment. Recover through the real HOME/Settings
        # controller route; never claim a no-op setup launch as submenu entry.
        item['setup_fallback']='ACTUAL_CONTROLLER_PATH_AFTER_INTENT_RETAINED_FRAGMENT'
        enter(a,item['path'])
        return
    for component in item['path'][len(prefix):]:
        top(a)
        try:seek_component(a,component)
        except RuntimeError:
            top(a);a.seek('高级',actionable=True);a.key('a');a.seek(component,actionable=True)
        a.key('a')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('plan',type=Path)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text(encoding='utf-8-sig'))
    results=[]; a=Audit()
    output=OUT/('followups-'+datetime.datetime.now().strftime('%H%M%S')+'.json')
    try:
        for item in plan:
            try:
                enter_supplement(a,item)
                full_path=['设置']+item['path']
                if item['action']=='graph':
                    value=graph(a,full_path,item.get('limit',700))
                    result=dict(item,status=value['status'])
                elif item['action']=='scan':
                    explorer=Explorer(a,'/'.join(item['path'])+'@'+output.stem)
                    if explorer.output.exists():raise ValueError('Fresh followup scan receipt required')
                    explorer.visit(full_path,item.get('dialog',False))
                    result=dict(item,status='SCAN_RECORDED',output=explorer.output.name)
                    if item.get('dialog',False):
                        entry=explorer.pages[0]['entry']
                        current=a.snap('followup-dialog-before-cancel')[3]
                        if current['window_id']!=entry['window_id']:
                            raise RuntimeError('Standalone dialog changed before its explicit cancel')
                        a.key('b')
                        for _ in range(10):
                            current=a.snap('followup-dialog-b-cancel')[3]
                            if current['window_id']!=entry['window_id']:break
                            time.sleep(.2)
                        else:raise RuntimeError('Standalone dialog B did not close')
                        result['actual_dialog_b_cancel']=current
                else: raise ValueError('Unknown followup action')
            except Exception as error:
                result=dict(item,status='ERROR',error=repr(error))
                print('FOLLOWUP_ERROR '+str(result),flush=True)
            results.append(result)
            output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            # A failed restoration or transport check leaves the current state
            # uncertain. Never continue pressing keys in another category.
            if result['status']=='ERROR' or result['status'] in ('RANGE_RESTORE_FAILED','DIRECTION_CHANGED_PAGE'):
                raise RuntimeError('Followup stopped safely: '+str(result))
    finally: a.close()

if __name__=='__main__': main()
