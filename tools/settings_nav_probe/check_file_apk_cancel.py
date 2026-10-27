"""Open an owned APK through Files, inspect installer controls, then cancel."""
import argparse
import hashlib
import json
import re
import subprocess
import time
from audit import Audit, OUT, adb, ADB, TARGET, descendants
from files import FIXTURE, enter_source, focus, open_control
from graph import graph

PACKAGE = 'com.roc.rgsp.audit.missingtarget'
INSTALLER = 'com.android.packageinstaller'
APP_OP = 'cmd appops {} com.android.documentsui REQUEST_INSTALL_PACKAGES{}'


def installer_button(a, text):
    # A dialog's initial ScrollView contains both labels. Matching a descendant
    # label can select that container instead of the requested real Button.
    data, root, _, _ = a.snap('installer-exact-button-lookup')
    buttons = [n for n in descendants(root) if n.get('visible') and
               n.get('class') == 'android.widget.Button' and n.get('text') == text]
    if len(buttons) != 1 or not buttons[0].get('id'):
        raise RuntimeError('Expected one enabled installer button: ' + text)
    state = focus(a, buttons[0]['id'].split('/')[-1], expected_package=INSTALLER)
    if state['focus'] != text or 'android.widget.Button' not in state['focus_signature']:
        raise RuntimeError('Installer button focus was not exact: ' + text)
    return state


def open_owned_fixture(a):
    # Reach lower grid rows with ordinary Down traversal before the generic
    # four-direction locator; its BFS can spend its bound revisiting upper
    # viewports while the final row is still off-screen.
    filename = 'zz_owned_installer_cancel.apk'
    for _ in range(40):
        _, root, node, state = a.snap('files-apk-find-lower-row')
        if state['package'] != 'com.android.documentsui':
            raise RuntimeError('Left Files before owned fixture lookup')
        if state['focus'] == filename and 'id/item_root' in (state['focus_signature'] or ''):
            a.key('a')
            return {'target': filename, 'before': state, 'after': a.snap('files-owned-apk-opened', True)[3]}
        rows = [n for n in descendants(root) if n.get('visible') and
                n.get('id') == 'com.android.documentsui:id/item_root' and
                any(c.get('text') == filename for c in descendants(n))]
        key = 'd'
        if rows and node and node.get('id') == 'com.android.documentsui:id/item_root':
            b = node['bounds']; t = rows[0]['bounds']
            x = (b[0] + b[2]) / 2
            # Align the column before moving vertically in a ragged last row.
            if x < t[0]: key = 'r'
            elif x > t[2]: key = 'l'
            else: key = 'd' if b[1] < t[1] else 'u'
        a.key(key)
    raise RuntimeError('Owned APK not visible after bounded native Down traversal')


def button_graph_verified(value, labels):
    """Accept a one-time initial ScrollView focus only after every button edge."""
    if value['status'] not in ('REACHABLE_FOCUS_GRAPH_SCANNED','REACHED_CONTROLS_WITH_PENDING_EDGES'):
        return False
    for label in labels:
        nodes=[key for key,state in value['nodes'].items() if state.get('focus')==label
               and 'android.widget.Button' in (state.get('focus_signature') or '')]
        if not nodes:return False
        if not any(all(any(e['from']==key and e['key']==direction for e in value['edges'])
                       for direction in ('u','d','l','r')) for key in nodes):return False
    return all('android.widget.ScrollView' in (value['nodes'][edge['node']].get('focus_signature') or '')
               and 'buttonPanel' in (value['nodes'][edge['node']].get('focus_signature') or '')
               for edge in value.get('unvisited_edges',[]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    output = OUT / ('files-apk-cancel-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh tag required')
    apk = OUT / 'fault-target/FaultTarget.apk'
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    remote = FIXTURE + '/source/zz_owned_installer_cancel.apk'
    result = {'status': 'RUNNING', 'install_confirmed': False}
    a = Audit()
    created = False
    changed_op = False
    try:
        a.key('wake')
        ui=adb('dumpsys activity service com.android.systemui/.SystemUIService')
        if re.search(r'^\s*mState=1 \(KGRD\)',ui,re.M):a.key('a')
        _,pending,_,pending_state=a.snap('files-apk-initial-scene')
        pending_labels={n.get('text') for n in descendants(pending) if n.get('visible')}
        if pending_state['package']==INSTALLER and {'继续','取消'}.issubset(pending_labels):
            # Cancel only the retained anonymous-source prompt from the owned
            # earlier test; no positive action is sent during recovery.
            installer_button(a,'取消');a.key('a')
            result['retained_prompt_a_cancel']=a.snap('files-apk-retained-prompt-canceled',True)[3]
            if result['retained_prompt_a_cancel']['package']!='com.android.documentsui':
                raise RuntimeError('Retained prompt cancel did not return to Files')
        if adb('pm path ' + PACKAGE + ' || true').strip():
            raise RuntimeError('Reserved fixture package is already installed')
        result['appop_before'] = adb(APP_OP.format('get', ''))
        if 'Default mode: default' not in result['appop_before'] and 'REQUEST_INSTALL_PACKAGES: default' not in result['appop_before']:
            raise RuntimeError('Unexpected preexisting install-source policy; preserved')
        if adb('if [ -e ' + remote + ' ]; then echo EXISTS; fi').strip():
            raise RuntimeError('Owned installer filename already exists; preserved')
        created = True
        subprocess.run([ADB, '-s', TARGET, 'push', str(apk), remote],
                       capture_output=True, check=True, timeout=30)
        if digest != adb('sha256sum ' + remote).split()[0]:
            raise RuntimeError('Fixture checksum mismatch')
        # Launch is setup only. The APK is opened via actual roots/row/A below.
        a.command('am start -n com.android.documentsui/.files.FilesActivity')
        time.sleep(.5)
        # ADB-created fixtures belong to the filesystem, not necessarily the
        # DownloadsProvider's indexed download database. Use the audited full
        # internal-storage root so enumeration does not depend on indexing.
        result['source'] = enter_source(a,root_label='RGSP H700')
        # Repeated owned-fixture recreation can leave the retained Files task's
        # directory loader cached. Refresh through the real menu before lookup.
        result['refresh_menu'] = focus(a, '更多选项')
        a.key('a')
        result['refresh_action'] = focus(a, '刷新')
        a.key('a')
        time.sleep(.5)
        result['open_blocked'] = open_owned_fixture(a)
        for _ in range(15):
            _, root, _, state = a.snap('files-apk-blocked', True)
            if state['package'] == INSTALLER:
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Installer did not open from the APK row')
        result['blocked_entry'] = state
        labels={n.get('text') for n in descendants(root) if n.get('visible')}
        unknown_prompt='设置' in labels and '安装' not in labels
        anonymous_prompt=({'继续','取消'}.issubset(labels) and '安装' not in labels
            and any('来历不明的应用' in str(v) for v in labels if v))
        if not unknown_prompt and not anonymous_prompt and not {'安装','取消'}.issubset(labels):
            raise RuntimeError('Unexpected installer prompt; no button activated')
        result['initial_prompt_kind']=('ANONYMOUS_SOURCE_CONTINUE_CANCEL' if anonymous_prompt else
            'UNKNOWN_SOURCE_SETTINGS_CANCEL' if unknown_prompt else 'DIRECT_INSTALL_CANCEL_TRUSTED_OR_ALLOWED_SOURCE')
        blocked=graph(a, ['文件', '未知来源提示', args.tag], 130)
        result['blocked_graph']=blocked['status']
        result['blocked_button_coverage']=button_graph_verified(blocked,{'取消','继续' if anonymous_prompt else '设置' if unknown_prompt else '安装'})
        if not result['blocked_button_coverage']:
            raise RuntimeError('Unknown-source prompt graph incomplete')
        installer_button(a, '取消')
        a.key('a')
        for _ in range(10):
            state = a.snap('files-apk-blocked-canceled')[3]
            if state['package'] == 'com.android.documentsui':
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Installer cancel did not return to Files')
        result['blocked_cancel'] = state
        # Reversible fixture setup only, never counted as controller evidence.
        if unknown_prompt:
            changed_op = True
            a.command(APP_OP.format('set', ' allow'))
        result['open_confirmation'] = open_owned_fixture(a)
        if anonymous_prompt:
            _,root,_,state=a.snap('files-apk-anonymous-reopened',True)
            labels={n.get('text') for n in descendants(root) if n.get('visible')}
            if state['package']!=INSTALLER or not {'继续','取消'}.issubset(labels):
                raise RuntimeError('Expected owned anonymous-source warning before Continue')
            result['anonymous_continue_focus']=installer_button(a,'继续')
            # AnonymousSourceDialog sets only an Activity-local allow flag and
            # calls initiateInstall(), which displays Install/Cancel. Never Install.
            a.key('a')
        for _ in range(15):
            _, root, _, state = a.snap('files-apk-confirmation', True)
            labels = {n.get('text') for n in descendants(root) if n.get('visible')}
            if state['package'] == INSTALLER and '安装' in labels and '取消' in labels:
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Expected owned APK install/cancel confirmation')
        result['confirmation_entry'] = state
        confirmation=graph(a, ['文件', '安装确认但不安装', args.tag], 150)
        result['confirmation_graph']=confirmation['status']
        result['confirmation_button_coverage']=button_graph_verified(confirmation,{'取消','安装'})
        if not result['confirmation_button_coverage']:
            raise RuntimeError('Install confirmation graph incomplete')
        result['install_focus_only'] = installer_button(a, '安装')
        installer_button(a, '取消')
        a.key('a')
        for _ in range(10):
            state = a.snap('files-apk-confirmation-canceled', True)[3]
            if state['package'] == 'com.android.documentsui':
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Install confirmation cancel did not return to Files')
        result['confirmation_cancel'] = state
        if adb('pm path ' + PACKAGE + ' || true').strip():
            raise RuntimeError('Fixture package unexpectedly installed')
        result['status'] = 'PASS_FILES_APK_EXPOSED_INSTALLER_BUTTONS_AND_A_CANCEL_NO_INSTALL'
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        try:
            if changed_op:
                result['policy_restore'] = a.command(APP_OP.format('set', ' default'))
                result['appop_after'] = adb(APP_OP.format('get', ''))
                if 'REQUEST_INSTALL_PACKAGES: allow' in result['appop_after']:
                    result['status'] = 'CLEANUP_FAILED'
                    raise RuntimeError('Install-source policy was not restored')
            if created:
                result['fixture_cleanup'] = a.command(
                    '[ "$(sha256sum ' + remote + ' | cut -d " " -f 1)" = ' + digest +
                    ' ] && rm ' + remote)
        finally:
            a.close()
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
