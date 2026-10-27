"""Check trusted-certificate lists/details and install entry, without trust changes."""
import argparse
import json
from audit import Audit, OUT, adb, descendants
from followup import enter, top
from files import focus
from graph import graph

PKG = 'com.android.settings'
TRUST = 'if [ -d /data/misc/keychain/cacerts-removed ]; then ls -la /data/misc/keychain/cacerts-removed; else echo NO_REMOVED_SYSTEM_CA_DIRECTORY; fi'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('credentials-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh tag required')
    a = Audit()
    result = {'status': 'RUNNING', 'trust_changes_submitted': False}
    try:
        result['trust_before'] = adb(TRUST)
        enter(a, ['安全', '加密与凭据', '信任的凭据'])
        top(a)
        walk = a.walk('trusted-ca-' + args.tag, 450)
        result['list_walk'] = {'steps': len(walk['path']), 'visited': len(walk['visited']),
                               'last': walk['path'][-1]}
        ca_rows = [s for s in walk['visited'].values()
                   if 'trusted_credential_status' not in (s.get('focus_signature') or '')
                   and ' / ' in (s.get('focus') or '')]
        result['reached_certificate_rows'] = [s['focus'] for s in ca_rows]
        if len(ca_rows) < 50:
            raise RuntimeError('Trusted CA list did not traverse a substantial system list')
        # Inspect the last real row; never confirm its status switch.
        _, root, node, state = a.snap('trusted-ca-bottom', True)
        if not node or node.get('checkable') or not any(
                n.get('id', '').endswith('/trusted_credential_subject_secondary') for n in descendants(node)):
            raise RuntimeError('End of CA list is not a real certificate row')
        result['detail_before'] = state
        a.key('a')
        _, root, _, result['detail_entry'] = a.snap('trusted-ca-detail', True)
        if result['detail_entry']['window_id'] == state['window_id']:
            raise RuntimeError('Certificate A did not open its detail dialog')
        scan = graph(a, ['安全凭据', args.tag, '证书详情'], 200)
        result['detail_graph'] = scan['status']
        result['detail_focuses'] = sorted({s.get('focus') or '' for s in scan['nodes'].values()})
        if scan['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED':
            raise RuntimeError('Certificate detail controls incomplete')
        a.key('b')
        result['detail_cancel'] = a.snap('trusted-ca-detail-cancel', True)[3]
        if result['detail_cancel']['window_id'] != state['window_id']:
            raise RuntimeError('Certificate details did not cancel to the list')
        top(a)
        focus(a, '用户', expected_package=PKG)
        a.key('a')
        result['user_tab'] = a.snap('trusted-ca-user-tab', True)[3]
        scan = graph(a, ['安全凭据', args.tag, '用户页签'], 90)
        result['user_graph'] = scan['status']
        if scan['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED':
            raise RuntimeError('User CA tab controls incomplete')
        enter(a, ['安全', '加密与凭据', '从存储设备安装'])
        result['install_entry'] = a.snap('credential-install-entry', True)[3]
        if result['install_entry']['package'] not in (PKG, 'com.android.certinstaller', 'com.android.documentsui', 'android'):
            raise RuntimeError('Unexpected certificate install entry')
        scan = graph(a, ['安全凭据', args.tag, '安装入口'], 180)
        result['install_graph'] = scan['status']
        if scan['status'] != 'REACHABLE_FOCUS_GRAPH_SCANNED':
            raise RuntimeError('Credential install entry controls incomplete')
        # No certificate or credential is selected/installed, and no lock is saved.
        result['install_return_path'] = []
        for _ in range(3):
            a.key('b')
            result['install_cancel'] = a.snap('credential-install-cancel', True)[3]
            result['install_return_path'].append(result['install_cancel'])
            if (result['install_cancel']['package'] == PKG
                    and result['install_cancel']['window'] == '加密与凭据'):
                break
        else:
            raise RuntimeError('Credential install entry did not cancel to its parent')
        result['trust_after'] = adb(TRUST)
        if result['trust_after'] != result['trust_before']:
            raise RuntimeError('System CA trust state changed')
        result['status'] = 'PASS_SYSTEM_CA_LIST_DETAILS_USER_TAB_INSTALL_ENTRY_FOCUS_CANCEL'
        print(result['status'], flush=True)
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
