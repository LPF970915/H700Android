"""Validate the declared no-touch capability through a native Contacts toolbar."""
import argparse
import datetime
import json
import re
import time
from audit import Audit, OUT, ROOT, adb, descendants
from graph import graph
from files import focus
from check_remaining_information_menus import exposed_button_coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum(): raise ValueError('Invalid tag')
    output = ROOT / 'out/native-no-touch-capability-20261027' / ('contacts-' + args.tag + '.json')
    if output.exists(): raise ValueError('Fresh evidence required')
    result = {'status': 'RUNNING', 'contact_changes': False, 'setup_only': 'Contacts Activity launch'}
    a = Audit()
    try:
        # Android's pm has-feature returns exit 1 for the expected false result.
        result['touchscreen_feature'] = adb('pm has-feature android.hardware.touchscreen || true').strip()
        if result['touchscreen_feature'] != 'false': raise RuntimeError('Touchscreen still advertised')
        result['policy_sha256'] = adb('sha256sum /vendor/etc/permissions/android.hardware.touchscreen.unavailable.xml').split()[0]
        if result['policy_sha256'] != '35a31dc53804a48aaf354890edf4fc7792bba8093deb9291e48ba4d939f095c2':
            raise RuntimeError('Unexpected capability policy')
        result['boot_id'] = adb('cat /proc/sys/kernel/random/boot_id').strip()
        a.key('wake')
        ui = adb('dumpsys activity service com.android.systemui/.SystemUIService')
        if re.search(r'^\s*mState=1 \(KGRD\)', ui, re.M): a.key('a')
        a.command('am start -W -n com.android.contacts/.activities.PeopleActivity')
        for _ in range(15):
            _, root, _, result['entry'] = a.snap('no-touch-contacts-ready', True)
            if result['entry']['package'] == 'com.android.contacts': break
            time.sleep(.2)
        else: raise RuntimeError('Contacts not ready')
        a.key('d')
        value = graph(a, ['无触屏能力', args.tag, '通讯录工具栏'], 180)
        result['graph_status'] = value['status']
        result['graph_path'] = value['path']
        result['buttons'] = exposed_button_coverage(value, 'com.android.contacts')
        if value['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED' or any(not b['reached'] for b in result['buttons']):
            raise RuntimeError('Contacts exposed buttons still not reachable')
        result['drawer_focus'] = focus(a, '打开抽屉式导航栏', expected_package='com.android.contacts')
        a.key('a')
        _, root, _, result['drawer_open'] = a.snap('no-touch-contacts-drawer-open', True)
        result['drawer_texts'] = sorted({n.get('text') for n in descendants(root) if n.get('visible') and n.get('text')})
        if '设置' not in result['drawer_texts']: raise RuntimeError('A did not open Contacts drawer')
        value = graph(a, ['无触屏能力', args.tag, '通讯录抽屉'], 220)
        result['drawer_graph_status'] = value['status']
        result['drawer_graph_path'] = value['path']
        if value['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED': raise RuntimeError('Drawer graph incomplete')
        a.key('b')
        _, root, _, result['drawer_closed'] = a.snap('no-touch-contacts-drawer-b-closed', True)
        if '设置' in {n.get('text') for n in descendants(root) if n.get('visible')}:
            raise RuntimeError('B did not close drawer')
        result['status'] = 'PASS_NO_TOUCH_FEATURE_CONTACTS_ALL_BUTTONS_DRAWER_A_GRAPH_B'
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        result['time'] = datetime.datetime.now().isoformat()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(result['status'], flush=True)


if __name__ == '__main__': main()
