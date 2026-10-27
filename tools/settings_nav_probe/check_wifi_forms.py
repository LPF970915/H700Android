"""Traverse unsaved Wi-Fi advanced/proxy/IP/EAP forms; never save a network."""
import argparse
import hashlib
import json
from pathlib import Path
from audit import Audit, OUT, adb, descendants
from followup import enter, top
from files import focus
from graph import graph

PKG = 'com.android.settings'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--resume-manual', type=Path,
                        help='Continue the same unsaved manual form after a graph-limit receipt')
    parser.add_argument('--resume-eap', type=Path,
                        help='Retain passed manual/PAC receipts and continue the same EAP entry')
    args = parser.parse_args()
    if not args.tag.replace('-', '').isalnum():
        raise ValueError('Invalid tag')
    if args.resume_manual and args.resume_eap:
        raise ValueError('Only one continuation is allowed')
    output = OUT / ('wifi-forms-' + args.tag + '.json')
    if output.exists():
        raise ValueError('Fresh tag required')
    a = Audit()
    result = {'status': 'RUNNING', 'network_saved': False, 'forms': []}
    try:
        result['wifi_before'] = adb('dumpsys wifi | grep mWifiInfo')

        def open_form():
            state = a.snap('wifi-form-parent-check')[3]
            if state['package'] != PKG or state['window'] != 'WLAN':
                enter(a, ['网络和互联网', 'WLAN'])
            top(a)
            a.seek('添加网络', actionable=True)
            a.key('a')
            data, _, _, state = a.snap('wifi-form-open', True)
            if any(w.get('type') == 2 for w in data['windows']):
                a.key('b')
            return state

        def choose(field, contains):
            focus(a, field, expected_package=PKG)
            a.key('a')
            _, root, _, state = a.snap('wifi-form-spinner', True)
            previous = None
            repeated = 0
            for _ in range(35):
                choices = list(dict.fromkeys(n.get('text') for n in descendants(root)
                               if n.get('visible') and n.get('text') and contains in n['text']))
                if choices:
                    break
                boundary = (state['focus_signature'], tuple((n.get('text'), tuple(n.get('bounds', [])))
                            for n in descendants(root) if n.get('visible') and n.get('text')))
                repeated = repeated + 1 if boundary == previous else 0
                if repeated >= 2:
                    break
                previous = boundary
                a.key('d')
                _, root, _, state = a.snap('wifi-form-spinner-scroll')
            if len(choices) != 1:
                raise RuntimeError('Spinner choice ambiguous: ' + field + ': ' + repr(choices))
            focus(a, choices[0], expected_package=PKG)
            a.key('a')
            return {'field': field, 'choice': choices[0], 'picker': state,
                    'applied': a.snap('wifi-form-spinner-applied', True)[3]}

        def spinner_menu(field):
            before = a.snap('wifi-dropdown-before')[3]
            a.key('a')
            _, _, _, entry = a.snap('wifi-dropdown-entry', True)
            if entry['window_id'] == before['window_id']:
                raise RuntimeError('Spinner did not open a distinct popup: ' + field)
            rows = []
            for direction in ('u', 'd', 'u'):
                last = None
                repeated = 0
                for _ in range(40):
                    _, _, _, state = a.snap('wifi-dropdown-' + direction)
                    if state['window_id'] != entry['window_id']:
                        raise RuntimeError('Direction left Wi-Fi dropdown: ' + field)
                    rows.append(state)
                    boundary = (state['focus_signature'], tuple(state.get('focus_bounds') or []))
                    repeated = repeated + 1 if boundary == last else 0
                    if repeated >= 2:
                        break
                    last = boundary
                    a.key(direction)
                else:
                    raise RuntimeError('Wi-Fi dropdown boundary not reached: ' + field)
            a.key('b')
            returned = a.snap('wifi-dropdown-cancel', True)[3]
            if returned['window_id'] != before['window_id']:
                raise RuntimeError('Dropdown B did not return to the same unsaved form')
            return {'field': field, 'entry': entry, 'rows': rows, 'returned': returned,
                    'status': 'PASS_BOTH_VERTICAL_DIRECTIONS_AND_B_NO_SELECTION'}

        def scan_form(name, required):
            # Reachability concerns controls, not every pixel offset of a long
            # scroll view. Walk its ordered fields and explicitly check peers.
            item = {'name': name, 'status': 'RUNNING', 'required': required,
                    'states': [], 'secondary_checks': [], 'dropdowns': []}
            result['forms'].append(item)
            top(a)
            reached = set()
            checked = set()
            previous = None
            repeated = 0
            dropdown_fields = {'security', 'metered_settings', 'proxy_settings', 'ip_settings',
                               'privacy_settings', 'hidden_settings', 'method', 'phase2',
                               'ca_cert', 'user_cert'}
            for step in range(180):
                _, root, node, state = a.snap('wifi-form-controls-' + str(step))
                if state['package'] != PKG or state['window'] != '添加网络':
                    raise RuntimeError('Direction left the unsaved Wi-Fi form')
                item['states'].append(state)
                node_id = node.get('id', '') if node else ''
                if node_id:
                    reached.add(node_id)
                short_id = node_id.rsplit('/', 1)[-1]
                if short_id in dropdown_fields and short_id not in checked:
                    checked.add(short_id)
                    item['dropdowns'].append(spinner_menu(short_id))
                    _, root, node, state = a.snap('wifi-form-dropdown-return')
                scanner_visible = any(n.get('visible') and n.get('id') == PKG + ':id/ssid_scanner_button'
                                      for n in descendants(root))
                if node_id == PKG + ':id/ssid' and not scanner_visible:
                    item['ssid_scanner_not_exposed_in_this_mode'] = True
                if node_id == PKG + ':id/ssid' and scanner_visible and 'ssid_scanner_button' not in checked:
                    checked.add('ssid_scanner_button')
                    a.key('r')
                    _, _, peer, peer_state = a.snap('wifi-ssid-scanner-focus', True)
                    if not peer or peer.get('id') != PKG + ':id/ssid_scanner_button':
                        raise RuntimeError('SSID scanner peer is not reachable with Right')
                    reached.add(peer['id'])
                    a.key('l')
                    _, root, node, state = a.snap('wifi-ssid-peer-return')
                    if not node or node.get('id') != node_id:
                        raise RuntimeError('SSID scanner Left did not return to the editor')
                    item['secondary_checks'].append({'target': peer_state, 'returned': state})
                if node_id == 'android:id/button2' and 'footer' not in checked:
                    checked.add('footer')
                    a.key('r')
                    _, _, peer, peer_state = a.snap('wifi-disabled-save-focus', True)
                    if not peer or peer.get('id') != 'android:id/button1' or peer.get('enabled'):
                        raise RuntimeError('Expected reachable disabled Save in an empty-SSID fixture')
                    reached.add(peer['id'])
                    a.key('l')
                    _, root, node, state = a.snap('wifi-footer-return')
                    if not node or node.get('id') != 'android:id/button2':
                        raise RuntimeError('Footer Left did not return to Cancel')
                    item['secondary_checks'].append({'target': peer_state, 'returned': state})
                geometry = tuple((n.get('id'), tuple(n.get('bounds', []))) for n in descendants(root)
                                 if n.get('visible') and (n.get('editable') or n.get('clickable')))
                boundary = (state['focus_signature'], tuple(state.get('focus_bounds') or []), geometry)
                repeated = repeated + 1 if boundary == previous else 0
                if repeated >= 2:
                    break
                previous = boundary
                a.key('d')
            else:
                raise RuntimeError('Wi-Fi semantic control walk did not reach its boundary')
            item['reached_ids'] = sorted(reached)
            item['missing'] = [field for field in required if PKG + ':id/' + field not in reached]
            if item['missing'] or 'android:id/button2' not in reached or 'android:id/button1' not in reached:
                raise RuntimeError('Wi-Fi semantic controls incomplete: ' + name + ': ' + repr(item['missing']))
            item['status'] = 'PASS_REQUIRED_FIELDS_DROPDOWNS_PEERS_AND_BOTH_FOOTERS'
            print('WIFI_FORM ' + name + ' ' + item['status'], flush=True)

        def cancel_form():
            # Read actual text and ID: never confuse a spinner option with Cancel.
            focus(a, '取消', expected_package=PKG)
            _, _, node, _ = a.snap('wifi-form-cancel-target')
            if node.get('id') != 'android:id/button2':
                raise RuntimeError('Unexpected form cancel target')
            a.key('a')
            state = a.snap('wifi-form-cancelled', True)[3]
            if state['window'] != 'WLAN':
                raise RuntimeError('Wi-Fi form did not cancel to WLAN')
            return state

        if args.resume_eap:
            raw = args.resume_eap.read_bytes()
            prior = json.loads(raw)
            if (len(prior['forms']) < 2 or any(not f['status'].startswith('PASS_') for f in prior['forms'][:2])
                    or any(f['name'] != '企业EAP' or f['status'] != 'RUNNING' for f in prior['forms'][2:])
                    or prior.get('network_saved') is not False):
                raise ValueError('Manual and PAC forms must have completed before EAP continuation')
            result['forms'] = prior['forms'][:2]
            result['continuation'] = {'source': args.resume_eap.name,
                                      'source_sha256': hashlib.sha256(raw).hexdigest()}
            _, _, _, state = a.snap('wifi-eap-continuation')
            if state['package'] != PKG:
                raise RuntimeError('EAP continuation is not in Settings')
            if state['window'] == '弹出式窗口':
                a.key('b')
                state = a.snap('wifi-eap-old-popup-closed')[3]
            if state['window_id'] != prior['eap_entry']['window_id']:
                raise RuntimeError('Not the same unfinished EAP form')
            result['eap_entry'] = state
        elif args.resume_manual:
            raw = args.resume_manual.read_bytes()
            prior = json.loads(raw)
            if (prior.get('network_saved') is not False or prior['forms'][0]['graph_status'] != 'GRAPH_LIMIT'
                    or prior['forms'][0]['missing']):
                raise ValueError('Only an all-targets-reached graph-limit receipt can continue')
            _, root, _, state = a.snap('wifi-manual-continuation', True)
            if state['package'] == 'com.android.systemui':
                a.key('wake')
                _, root, _, state = a.snap('wifi-manual-continuation-awake', True)
                if any('global_actions' in n.get('id', '') for n in descendants(root)):
                    raise RuntimeError('Power menu is open; refusing an ambiguous unlock A')
                if state['package'] == 'com.android.systemui':
                    a.key('a')
                    _, root, _, state = a.snap('wifi-manual-continuation-a-unlocked', True)
                result['resume_after_a_unlock'] = state
            result['manual_entry'] = state
            if result['manual_entry']['window_id'] != prior['manual_entry']['window_id']:
                raise RuntimeError('Not the same unfinished manual form')
            for field, text in [('proxy_settings', '手动'), ('ip_settings', '静态')]:
                node = next(n for n in descendants(root) if n.get('id') == PKG + ':id/' + field)
                if text not in [n.get('text') for n in descendants(node)]:
                    raise RuntimeError('Manual-form selection changed before continuation')
            result['continuation'] = {'source': args.resume_manual.name,
                                      'source_sha256': hashlib.sha256(raw).hexdigest()}
        else:
            result['manual_entry'] = open_form()
            focus(a, 'wifi_advanced_togglebox', expected_package=PKG)
            a.key('a')
            result['manual_proxy'] = choose('proxy_settings', '手动')
            result['static_ip'] = choose('ip_settings', '静态')
        if not args.resume_eap:
            scan_form('手动代理和静态IP', ['ssid', 'security', 'proxy_settings', 'proxy_hostname',
                      'proxy_port', 'proxy_exclusionlist', 'ip_settings', 'ipaddress', 'gateway',
                      'network_prefix_length', 'dns1', 'dns2', 'hidden_settings'])
            result['manual_cancel'] = cancel_form()
            result['pac_entry'] = open_form()
            focus(a, 'wifi_advanced_togglebox', expected_package=PKG)
            a.key('a')
            result['pac_proxy'] = choose('proxy_settings', '自动配置')
            scan_form('PAC代理', ['proxy_settings', 'proxy_pac', 'ip_settings', 'hidden_settings'])
            result['pac_cancel'] = cancel_form()
            result['eap_entry'] = open_form()
        result['eap_security'] = choose('security', 'WPA/WPA2/WPA3-Enterprise')
        result['eap_ca'] = choose('ca_cert', '使用系统证书')
        scan_form('企业EAP', ['method', 'phase2', 'ca_cert', 'domain', 'identity', 'anonymous', 'password'])
        result['eap_cancel'] = cancel_form()
        result['wifi_after'] = adb('dumpsys wifi | grep mWifiInfo')
        if 'SSID: Xiaomi_0421,' not in result['wifi_after'] or 'Supplicant state: COMPLETED' not in result['wifi_after']:
            raise RuntimeError('Original Wi-Fi connection not retained')
        result['status'] = 'PASS_MANUAL_PROXY_STATIC_IP_PAC_EAP_FORMS_AND_CANCEL_NO_NETWORK_SAVED'
        print(result['status'], flush=True)
    except Exception as error:
        result.update(status='ERROR', error=repr(error))
        raise
    finally:
        a.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
