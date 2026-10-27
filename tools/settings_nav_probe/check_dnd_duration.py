"""Exercise DND duration controls using HAT/A, then cancel without saving."""
import argparse
import json
from audit import Audit, OUT, adb, descendants
from followup import enter
from files import focus
from graph import graph

PKG = 'com.android.settings'
QUERY = 'settings get secure zen_duration; settings get global zen_mode; settings get global zen_mode_config_etag'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    target = OUT / ('dnd-duration-' + args.tag + '.json')
    if target.exists():
        raise ValueError('Fresh tag required')
    a = Audit()
    result = {'status': 'RUNNING', 'settings_submitted': False}
    try:
        result['policy_before'] = adb(QUERY)
        enter(a, ['声音', '勿扰模式', '默认时长'])
        _, root, _, result['entry'] = a.snap('dnd-duration-entry', True)
        radios = [n for n in descendants(root) if n.get('visible') and n.get('checkable')]
        if len(radios) != 3:
            raise RuntimeError('Expected three duration radio choices')
        scan = graph(a, ['勿扰时长', args.tag], 220)
        result['graph_status'] = scan['status']
        reached = {tuple(s.get('focus_bounds') or []) for s in scan['nodes'].values()}
        result['missing_radios'] = [n['bounds'] for n in radios if tuple(n['bounds']) not in reached]
        if scan['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED' or result['missing_radios']:
            raise RuntimeError('DND duration focus graph incomplete')
        for title in ('每次都询问', '直到您将其关闭'):
            focus(a, title, expected_package=PKG)
            a.key('a')
            _, root, _, state = a.snap('dnd-duration-radio-applied', True)
            checked = [n['bounds'] for n in descendants(root) if n.get('visible') and n.get('checkable') and n.get('checked')]
            result.setdefault('radio_actions', []).append({'target': title, 'checked': checked, 'state': state})
            index = 2 if title == '每次都询问' else 0
            if checked != [radios[index]['bounds']]:
                raise RuntimeError('A did not select the requested duration radio')
        def text_lines(root):
            return [n.get('text') for n in descendants(root) if n.get('visible') and n.get('id') == 'android:id/text1']
        _, root, _, _ = a.snap('dnd-duration-before-plus')
        before = text_lines(root)
        focus(a, '增加时间。', expected_package=PKG)
        a.key('a')
        _, root, _, result['plus'] = a.snap('dnd-duration-plus', True)
        result['duration_before'] = before
        result['duration_plus'] = text_lines(root)
        if result['duration_plus'] == before:
            raise RuntimeError('Plus A did not change the dialog duration')
        focus(a, '减少时间。', expected_package=PKG)
        a.key('a')
        _, root, _, result['minus'] = a.snap('dnd-duration-minus', True)
        if text_lines(root) != before:
            raise RuntimeError('Minus A did not restore the dialog duration')
        # Match the footer by text, not button2, which also identifies plus.
        focus(a, '取消', expected_package=PKG)
        a.key('a')
        result['cancel'] = a.snap('dnd-duration-cancel', True)[3]
        if result['cancel']['window'] != '勿扰模式':
            raise RuntimeError('Cancel did not return to DND settings')
        result['policy_after'] = adb(QUERY)
        if result['policy_after'] != result['policy_before']:
            raise RuntimeError('DND settings changed despite cancellation')
        result['status'] = 'PASS_ALL_RADIOS_PLUS_MINUS_FOOTERS_AND_CANCEL_POLICY_UNCHANGED'
        print(result['status'], flush=True)
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
