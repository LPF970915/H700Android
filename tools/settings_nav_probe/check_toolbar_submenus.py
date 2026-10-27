"""Review children of previously missed overflow menus without committing actions."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from audit import Audit, OUT, adb, descendants, label
from followup import enter
from files import focus
from graph import graph
from check_remaining_information_menus import exposed_button_coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--resume-receipt', type=Path)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--legal-parent-setup',action='store_true',help='Reuse proven Settings parent entry and launch that same legal dashboard as setup')
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('toolbar-submenus-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh evidence required')
    result = {'status': 'RUNNING', 'items': [], 'destructive_actions_confirmed': False,
              'source_review': 'ZenModeAutomationSettings deletes only positive action; PowerUsageAdvanced overflow toggles display filter only; AddManualPrinterDialog adds only positive click/editor action, neither used. No printer connection or print job.'}
    a = Audit()
    baseline = 'settings get global zen_mode; settings get global zen_mode_config_etag; settings get secure lock_screen_lock_after_timeout'

    def save():
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')

    def scene(name, package, expected_window=None):
        # WebView Activity teardown can lag the B event. Observe the return;
        # never replay B into the eventual parent page.
        for _ in range(16 if name=='legal-b-return' else 1):
            data, root, node, state = a.snap('toolbar-submenus-' + name, True)
            has_title = (not expected_window or state['window'] == expected_window
                         or any(n.get('visible') and n.get('text') == expected_window
                                for n in descendants(root)))
            if state['package'] == package and has_title:
                return data, root, node, state
            time.sleep(.25)
        raise RuntimeError('Unexpected scene: ' + str(state))

    def scan(path, package, title=None):
        data, root, node, entry = scene('entry', package, title)
        item = {'path': path, 'entry': entry}
        result['items'].append(item)
        save()
        if any(w.get('type') == 2 for w in data['windows']):
            a.key('b')
        a.key('d')
        value = graph(a, ['工具栏子菜单', args.tag] + path, 450)
        item['graph_status'] = value['status']
        item['graph_path'] = value['path']
        item['exposed_buttons'] = exposed_button_coverage(value, package)
        item['focused_labels'] = sorted({s.get('focus') or '' for s in value['nodes'].values()})
        if value['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED':
            raise RuntimeError('Incomplete submenu graph: ' + '/'.join(path))
        if any(not b['reached'] for b in item['exposed_buttons']):
            raise RuntimeError('Exposed button not reached: ' + '/'.join(path))
        item['status'] = 'PASS_ACTUAL_A_ENTRY_FOUR_DIRECTION_GRAPH'
        save()
        return item

    def cancel(item, package, title=None):
        data = a.snap('toolbar-submenus-before-b')[0]
        if any(w.get('type') == 2 for w in data['windows']):
            a.key('b')
            if any(w.get('type') == 2 for w in a.snap('toolbar-submenus-ime-hidden')[0]['windows']):
                raise RuntimeError('IME did not hide')
        a.key('b')
        item['b_return'] = scene('b-return', package, title)[3]
        if item['b_return']['window_id'] == item['entry']['window_id']:
            raise RuntimeError('B did not close submenu')
        item['status'] = 'PASS_ACTUAL_A_GRAPH_B_CANCEL_NO_COMMIT'
        save()

    try:
        result['baseline'] = adb(baseline)
        if args.resume_receipt:
            if not args.stage: raise ValueError('Pinned stage required for continuation')
            previous=json.loads(args.resume_receipt.read_text(encoding='utf8'))
            if previous['status']!='ERROR' or previous['baseline']!=result['baseline']:
                raise RuntimeError('Continuation baseline mismatch')
            if len(previous['items'])<5 or any(x.get('status')!='PASS_ACTUAL_A_GRAPH_B_CANCEL_NO_COMMIT' for x in previous['items']):
                raise RuntimeError('Cannot reuse incomplete submenu entries')
            components=json.loads((args.stage/'components.json').read_text())
            result['continuation_component_checks']={}
            for key,package in [
                ('system:/system/product/priv-app/Settings/Settings.apk','com.android.settings'),
                ('system:/system/app/RGSPNavigation/RGSPNavigation.apk','com.roc.rgsp.navtrial')]:
                active=adb('pm path '+package).strip().removeprefix('package:')
                digest=adb('sha256sum '+active).split()[0]
                if digest!=components[key]:raise RuntimeError('Continuation component changed')
                result['continuation_component_checks'][key]=digest
            for key,active in [('system:/system/framework/framework-res.apk','/system/framework/framework-res.apk'),('vendor:/etc/permissions/android.hardware.touchscreen.unavailable.xml','/vendor/etc/permissions/android.hardware.touchscreen.unavailable.xml')]:
                digest=adb('sha256sum '+active).split()[0]
                if digest!=components[key]:raise RuntimeError('Continuation resource/policy changed')
                result['continuation_component_checks'][key]=digest
            if adb('sha256sum /system/app/BuiltInPrintService/BuiltInPrintService.apk').split()[0]!='7bbf3d6a387b574c9e57652c5fc37843a1ddca2e17ffd60a3a7d4dc6c19a539c':
                raise RuntimeError('Print service changed')
            result['items']=previous['items']
            result['wifi_direct_search_visible']=previous['wifi_direct_search_visible']
            result['continuation']={'file':str(args.resume_receipt),'sha256':hashlib.sha256(args.resume_receipt.read_bytes()).hexdigest(),'scope':'Only completed menu A/graphs/B retained; failed legal viewer observation is rerun with bounded external-document DOM.'}
            save()
        else:
            path = ['声音', '勿扰模式', '时间安排', '更多选项', '删除时间表']
            enter(a, path)
            item = scan(path, 'com.android.settings', '删除时间表')
            cancel(item, 'com.android.settings', '时间安排')

            path = ['电池', '更多选项', '电池用量']
            enter(a, path)
            item = scan(path, 'com.android.settings', '电池用量')
            focus(a, '更多选项', expected_package='com.android.settings')
            a.key('a')
            popup = scan(path + ['更多选项'], 'com.android.settings', '弹出式窗口')
            cancel(popup, 'com.android.settings', '电池用量')
            cancel(item, 'com.android.settings', '电池')

            path = ['已连接的设备', '连接偏好设置', '打印', '默认打印服务', '更多选项', '添加打印机']
            enter(a, path)
            item = scan(path, 'com.android.bips', '添加打印机')
            focus(a, '根据 IP 地址添加打印机', expected_package='com.android.bips')
            a.key('a')
            dialog = scan(path + ['根据 IP 地址添加打印机'], 'com.android.bips', '根据 IP 地址添加打印机')
            cancel(dialog, 'com.android.bips', '添加打印机')
            # Wi-Fi Direct search is conditional on service permission/state. Do not
            # enable it or grant permissions just to create additional UI coverage.
            _, root, _, _ = scene('printer-conditional-options', 'com.android.bips', '添加打印机')
            present = any(n.get('visible') and label(n) == '查找 WLAN 直连打印机'
                          for n in descendants(root))
            result['wifi_direct_search_visible'] = present
            if present:
                focus(a, '查找 WLAN 直连打印机', expected_package='com.android.bips')
                a.key('a')
                direct = scan(path + ['查找 WLAN 直连打印机'], 'com.android.bips')
                cancel(direct, 'com.android.bips', '添加打印机')
            cancel(item, 'com.android.settings', '默认打印服务')

        # These old rows were focused but not activated by the original menu
        # classifier. Test their local read-only viewers, without treating the
        # complete license text or every embedded HTML link as a Settings menu.
        result['legal_viewers'] = []
        for name in ('第三方许可', '系统 WebView 许可'):
            if args.legal_parent_setup:
                if not args.resume_receipt:raise ValueError('Parent entry evidence required before setup reuse')
                command="am start -n 'com.android.settings/.Settings$LegalSettingsActivity'"
                a.command(command)
            else:
                enter(a, ['关于手机', '法律信息'])
            parent = scene('legal-parent', 'com.android.settings', '法律信息')[3]
            before = focus(a, name, expected_package='com.android.settings')
            a.key('a')
            for _ in range(16):
                data, root, _, opened = a.snap('toolbar-legal-open', True)
                if opened['window_id'] != parent['window_id'] and opened['package']:
                    break
                time.sleep(.3)
            else:
                raise RuntimeError('Legal viewer did not open: ' + name)
            viewer = {'name': name, 'a_focus': before, 'entry': opened, 'directions': []}
            if args.legal_parent_setup:viewer['setup_command']=command
            result['legal_viewers'].append(viewer)
            save()
            buttons = {}
            for direction in ('d', 'u', 'l', 'r'):
                a.key(direction)
                data, root, _, state = a.snap('toolbar-legal-' + direction)
                if state['package'] != opened['package']:
                    raise RuntimeError('Direction left license viewer')
                viewer['directions'].append(state)
                for node in descendants(root):
                    if (node.get('visible') and node.get('enabled') and node.get('clickable')
                            and node.get('class', '').endswith('Button')):
                        buttons[(node.get('id') or label(node))] = label(node)
            viewer['native_buttons'] = []
            for resource, text in buttons.items():
                target = resource.split('/')[-1] if '/' in resource else text
                found = focus(a, target, expected_package=opened['package'])
                viewer['native_buttons'].append({'id': resource, 'label': text, 'focus': found})
            a.key('b')
            viewer['b_return'] = scene('legal-b-return', 'com.android.settings', '法律信息')[3]
            viewer['status'] = 'PASS_A_LOCAL_LICENSE_VIEWER_DIRECTIONS_BUTTON_FOCUS_B'
            save()
        result['after'] = adb(baseline)
        if result['baseline'] != result['after']:
            raise RuntimeError('Read-only submenu baseline changed')
        result['status'] = 'PASS_OVERFLOW_CHILDREN_HAT_A_GRAPH_B_NO_DELETE_OR_PRINTER_ADD'
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        save()
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
