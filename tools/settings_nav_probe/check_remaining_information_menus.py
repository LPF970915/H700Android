"""Controller entry, direction coverage and cancellation for source-reviewed gaps."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from audit import Audit, OUT, adb, descendants, label
from followup import enter_supplement
from explore import in_toolbar
from graph import graph


def exposed_button_coverage(value, package):
    """A closed graph alone cannot prove every visible native button was reached."""
    buttons = {}
    for state in [value['entry']] + list(value['nodes'].values()):
        data = json.loads((OUT / state['file']).read_text(encoding='utf8'))
        for window in data['windows']:
            root = window.get('root', {})
            if (window.get('type') != 1 or window.get('id') != state['window_id']
                    or root.get('package') != package):
                continue
            for node in descendants(root):
                kind = node.get('class', '')
                if (node.get('visible') and node.get('enabled') and node.get('clickable')
                        and (kind.endswith('Button') or in_toolbar(root, node))):
                    text = label(node)
                    key = (node.get('id', ''), kind, text)
                    buttons[key] = {'id': key[0], 'class': kind, 'label': text}
    reached = list(value['nodes'].values())
    for (resource, kind, text), button in buttons.items():
        button['reached'] = any(state.get('focus') == text
            and kind in (state.get('focus_signature') or '')
            and (not resource or resource in (state.get('focus_signature') or ''))
            for state in reached)
    return list(buttons.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--resume-receipt', type=Path)
    parser.add_argument('--stage', type=Path)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('remaining-information-menus-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh evidence required')
    plan = [
        (['无障碍', 'RGSP D-pad Navigation'], None, 'com.android.settings'),
        (['隐私权', '使用无障碍功能'], None, 'com.android.permissioncontroller'),
        (['电池', '应用正常运行中'], None, 'com.android.settings'),
        (['系统', '开发者选项', '错误报告'], 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS', 'com.android.settings'),
        (['系统', '开发者选项', '最小宽度'], 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS', 'com.android.settings'),
        (['系统', '开发者选项', '待机应用', 'WebView Browser Tester'], 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS', 'com.android.settings'),
        (['系统', '开发者选项', '系统跟踪'], 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS', 'com.android.traceur'),
        (['系统', '开发者选项', '系统跟踪', '类别'], 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS', 'com.android.traceur'),
        (['系统', '开发者选项', '系统跟踪', '每个 CPU 的缓冲区空间'], 'android.settings.APPLICATION_DEVELOPMENT_SETTINGS', 'com.android.traceur'),
        (['网络和互联网', 'WLAN', 'WLAN 偏好设置', 'WLAN 直连', '更多选项', '重命名设备'], 'android.settings.WIFI_SETTINGS', 'com.android.settings'),
        (['网络和互联网', 'WLAN', 'Xiaomi_0421', '修改'], 'android.settings.WIFI_SETTINGS', 'com.android.settings'),
        (['网络和互联网', 'WLAN', 'Xiaomi_0421', '添加设备'], 'android.settings.WIFI_SETTINGS', 'com.android.settings'),
        (['应用和通知', '查看全部 21 个应用', '日历', '电池', '后台限制'], None, 'com.android.settings'),
        (['声音', '勿扰模式', '通话', '已加星标的联系人'], None, 'com.android.contacts'),
    ]
    result = {'status': 'RUNNING', 'items': [], 'positive_dialog_actions': False,
              'source_review': 'DensityPreference commits only positive close; InactiveApps bucket chooser changes only selected value; BugreportPreference reports only positive action; SummaryTip dialog OK has null listener; Wi-Fi rename/modify and background restriction canceled with B; Contacts link opens existing viewer only.'}
    a = Audit()
    baseline_query = ('settings get secure enabled_accessibility_services; '
                      'settings get secure accessibility_enabled; wm density; '
                      'am get-standby-bucket org.chromium.webview_shell')
    try:
        result['baseline'] = adb(baseline_query)
        if args.resume_receipt:
            if not args.stage:
                raise ValueError('Pinned stage required for information-menu continuation')
            old = json.loads(args.resume_receipt.read_text(encoding='utf8'))
            if old['status'] != 'ERROR' or old.get('baseline') != result['baseline']:
                raise RuntimeError('Continuation baseline changed')
            staged = json.loads((args.stage / 'components.json').read_text(encoding='utf8'))
            result['continuation_component_checks'] = {}
            for component, package in [
                ('system:/system/product/priv-app/Settings/Settings.apk', 'com.android.settings'),
                ('system:/system/app/RGSPNavigation/RGSPNavigation.apk', 'com.roc.rgsp.navtrial'),
                ('system:/system/priv-app/PermissionController/PermissionController.apk', 'com.android.permissioncontroller')]:
                active = adb('pm path ' + package).strip().removeprefix('package:')
                digest = adb('sha256sum ' + active).split()[0]
                if digest != staged[component]:
                    raise RuntimeError('Active component changed before information continuation')
                result['continuation_component_checks'][component] = digest
            completed = [item for item in old['items'] if
                item.get('status') == 'PASS_ACTUAL_ENTRY_FOUR_DIRECTIONS_B_NO_SETTING_CHANGE'
                and item.get('graph') == 'REACHABLE_FOCUS_GRAPH_SCANNED'
                and all(button['reached'] for button in item.get('exposed_buttons', []))]
            result['items'].extend(completed)
            done = {tuple(item['path']) for item in completed}
            plan = [item for item in plan if tuple(item[0]) not in done]
            result['continuation'] = {'file': str(args.resume_receipt),
                'sha256': hashlib.sha256(args.resume_receipt.read_bytes()).hexdigest(),
                'scope': 'Only completed A/graph/B items reused; failed items rerun against the same pinned components.'}
            failed = old['items'][-1]
            data, _, _, current = a.snap('remaining-menu-continuation-scene')
            if (failed.get('entry', {}).get('window_id') == current['window_id']
                    and failed.get('entry', {}).get('package') == current['package']
                    and failed.get('entry', {}).get('window') == current['window']):
                if any(w.get('type') == 2 for w in data['windows']): a.key('b')
                a.key('b')
                result['retained_failed_menu_b_cancel'] = a.snap('remaining-menu-continuation-cancel', True)[3]
                if result['retained_failed_menu_b_cancel']['window_id'] == current['window_id']:
                    raise RuntimeError('Retained failed menu did not cancel')
        for path, setup, expected_package in plan:
            item = {'path': path, 'setup_action': setup}
            result['items'].append(item)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
            item['setup'] = {'path': path, 'setup_action': setup}
            enter_supplement(a, item['setup'])
            data, _, _, item['entry'] = a.snap('remaining-menu-entry', True)
            if not item['entry']['package']:
                item['transition_observations'] = [item['entry']]
                for _ in range(12):
                    time.sleep(.2)
                    data, _, _, item['entry'] = a.snap('remaining-menu-entry-settle', True)
                    item['transition_observations'].append(item['entry'])
                    if item['entry']['package']: break
            if item['entry']['package'] != expected_package:
                raise RuntimeError('Unexpected package at ' + '/'.join(path))
            if any(w.get('type') == 2 for w in data['windows']):
                a.key('b')
            # Initialize native input focus before closing the direction graph;
            # the entry snapshot separately preserves any one-time container.
            a.key('d')
            item['initial_direction'] = a.snap('remaining-menu-initial-direction')[3]
            value = graph(a, ['剩余信息菜单', args.tag] + path, 450)
            item['graph'] = value['status']
            item['graph_path'] = value['path']
            item['exposed_buttons'] = exposed_button_coverage(value, expected_package)
            if item['graph'] != 'REACHABLE_FOCUS_GRAPH_SCANNED':
                # Transient native initial focus may have no return edge. This
                # remains explicit evidence, never silently counted as closed.
                raise RuntimeError('Incomplete information-menu graph: ' + '/'.join(path))
            if any(not button['reached'] for button in item['exposed_buttons']):
                raise RuntimeError('Visible native button not reached: ' + '/'.join(path))
            final_data, _, _, _ = a.snap('remaining-menu-before-b')
            if any(w.get('type') == 2 for w in final_data['windows']):
                a.key('b')
                if any(w.get('type') == 2 for w in a.snap('remaining-menu-ime-hidden')[0]['windows']):
                    raise RuntimeError('B did not hide the uncommitted editor keyboard')
            a.key('b')
            item['b_return'] = a.snap('remaining-menu-b-return', True)[3]
            if item['b_return']['window_id'] == item['entry']['window_id']:
                raise RuntimeError('B did not leave reviewed menu: ' + '/'.join(path))
            item['status'] = 'PASS_ACTUAL_ENTRY_FOUR_DIRECTIONS_B_NO_SETTING_CHANGE'
        result['after'] = adb(baseline_query)
        if result['baseline'] != result['after']:
            raise RuntimeError('Read-only menu baseline changed')
        result['status'] = 'PASS_REMAINING_INFORMATION_MENUS_HAT_A_ENTRY_B_CANCEL'
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
