"""Cover horizontal App info/storage buttons without invoking their actions."""
import argparse
import json
from audit import Audit, OUT, descendants, label
from files import focus
from followup import top


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tag', required=True)
    args = p.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('app-action-rows-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh evidence required')
    a = Audit()
    result = {'status': 'RUNNING', 'apps': [], 'destructive_button_confirmations': 0}
    def save():
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    def buttons(scope):
        _, root, _, _ = a.snap('app-action-row-visible')
        controls = [n for n in descendants(root) if n.get('visible') and
                    n.get('class') == 'android.widget.Button' and
                    n.get('id', '').startswith('com.android.settings:id/button')]
        found = []
        for node in controls:
            item = {'id': node['id'], 'label': label(node), 'enabled': node.get('enabled')}
            if node.get('enabled'):
                item['focus'] = focus(a, node['id'].split('/')[-1], expected_package='com.android.settings')
                if item['focus']['focus'] != item['label']:
                    raise RuntimeError('App action row matched a different button')
            else:
                item['disposition'] = 'NATIVE_DISABLED_RECORDED_NOT_ACTIVATED'
            found.append(item)
        if not found:
            raise RuntimeError('No native action buttons at ' + scope)
        return found
    try:
        # Parent intent is setup only; all installed rows and children use HAT/A/B.
        a.command("am start -n 'com.android.settings/.Settings$AppAndNotificationDashboardActivity'")
        top(a)
        # This centered header button is below the middle recent-app column.
        # A vertical-only seek from the left column legitimately bypasses it.
        focus(a, 'header_details', expected_package='com.android.settings')
        a.key('a')
        top(a)
        names = []
        repeated = 0
        previous = None
        for _ in range(160):
            _, root, node, state = a.snap('app-action-list-inventory')
            if node and node.get('clickable'):
                titles = [n.get('text') for n in descendants(node)
                          if n.get('id') == 'android:id/title' and n.get('text')]
                if len(titles) == 1 and titles[0] not in names:
                    names.append(titles[0])
            repeated = repeated + 1 if state['focus_signature'] == previous else 0
            if repeated >= 2:
                break
            previous = state['focus_signature']
            a.key('d')
        else:
            raise RuntimeError('App list boundary not reached')
        if len(names) < 15:
            raise RuntimeError('Unexpectedly small installed-app inventory')
        result['inventory'] = names
        top(a)
        for name in names:
            a.seek(name, actionable=True)
            a.key('a')
            _, root, _, state = a.snap('app-action-detail-entry', True)
            if state['window'] != '应用信息' or not any(
                    n.get('id', '').endswith('/entity_header_title') and n.get('text') == name
                    for n in descendants(root)):
                raise RuntimeError('Wrong app detail for ' + name)
            item = {'name': name, 'entry': state}
            result['apps'].append(item)
            item['app_info_buttons'] = buttons('app info')
            a.seek('存储和缓存', actionable=True)
            a.key('a')
            item['storage_entry'] = a.snap('app-action-storage-entry', True)[3]
            item['storage_buttons'] = buttons('storage and cache')
            a.key('b')
            returned = a.snap('app-action-storage-b-return')[3]
            if returned['window_id'] != state['window_id']:
                raise RuntimeError('Storage B did not return to app detail')
            a.key('b')
            item['list_return'] = a.snap('app-action-detail-b-return')[3]
            if item['list_return']['window'] != '应用信息':
                raise RuntimeError('App detail B did not return to app list')
            item['status'] = 'PASS_ALL_EXPOSED_ENABLED_APP_STORAGE_BUTTONS_FOCUSED_NO_ACTION'
            save()
        result['status'] = 'PASS_INSTALLED_APP_HORIZONTAL_ACTION_ROWS_NO_DESTRUCTIVE_CONFIRM'
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        save()
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
