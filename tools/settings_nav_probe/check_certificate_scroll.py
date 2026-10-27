"""Verify direction-only Settings text panes reach certificate fingerprints."""
import argparse
import json
from audit import Audit, OUT, adb, descendants
from followup import enter
from files import focus
from graph import graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('certificate-scroll-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh tag required')
    a = Audit()
    result = {'status': 'RUNNING', 'trust_changes_submitted': False}
    try:
        enter(a, ['安全', '加密与凭据', '信任的凭据'])
        focus(a, 'Chambers of Commerce Root - 2008', expected_package='com.android.settings')
        _, _, node, result['row'] = a.snap('certificate-scroll-row', True)
        if not node or node.get('checkable') or not any(
                n.get('id', '').endswith('/trusted_credential_subject_secondary') for n in descendants(node)):
            raise RuntimeError('Certificate row is not an independent detail action')
        a.key('a')
        _, _, _, result['entry'] = a.snap('certificate-scroll-entry', True)
        visible_ids = set()
        pane_states = []
        def guard(root, node, state):
            visible_ids.update(n.get('id') for n in descendants(root) if n.get('visible') and n.get('text'))
            if node and node.get('class', '').endswith('ScrollView'):
                pane_states.append(state)
                if node.get('clickable'):
                    raise RuntimeError('Read-only certificate pane unexpectedly clickable')
        scan = graph(a, ['证书滚动区', args.tag], 450, guard=guard)
        result['graph_status'] = scan['status']
        required = {'android:id/issued_on', 'android:id/expires_on',
                    'android:id/sha256_fingerprint', 'android:id/sha1_fingerprint'}
        result['missing_information'] = sorted(required - visible_ids)
        result['pane_states'] = pane_states
        if scan['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED' or result['missing_information'] or not pane_states:
            raise RuntimeError('Certificate body cannot be completely traversed with directions')
        result['focuses'] = sorted({s.get('focus') or '' for s in scan['nodes'].values()})
        if '停用' not in result['focuses'] or '确定' not in result['focuses']:
            raise RuntimeError('Certificate body prevents reaching the footer controls')
        # A on the read-only pane must remain inert. Locate it through its text.
        for title in ('颁发给：', '指纹', '有效期：'):
            try:
                focus(a, title, expected_package='com.android.settings')
                _, _, node, state = a.snap('certificate-pane-confirm-guard')
                if node and node.get('class', '').endswith('ScrollView'):
                    break
            except RuntimeError:
                continue
        else:
            raise RuntimeError('Read-only body target cannot be reselected')
        service = adb('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        import re
        count = re.search(r'actionCount=(\d+)', service)[1]
        a.key('a')
        _, _, _, result['inert_a'] = a.snap('certificate-pane-inert-a', True)
        after = adb('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        if re.search(r'actionCount=(\d+)', after)[1] != count or result['inert_a']['window_id'] != state['window_id']:
            raise RuntimeError('A activated a read-only certificate pane')
        a.key('b')
        result['cancel'] = a.snap('certificate-scroll-cancel', True)[3]
        if result['cancel']['window'] != '信任的凭据':
            raise RuntimeError('Certificate detail did not cancel to its list')
        result['status'] = 'PASS_SCROLL_BODY_VALIDITY_BOTH_FINGERPRINTS_FOOTERS_A_INERT_B_RETURN'
        print(result['status'], flush=True)
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
