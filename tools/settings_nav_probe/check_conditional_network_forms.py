"""Reach conditional private-DNS and EAP-TLS controls; cancel both owned forms."""
import argparse
import json
import time
from audit import Audit, OUT, adb, descendants
from followup import enter_supplement, top
from files import focus
from graph import graph
from explore import Explorer
from ime_keys import type_ascii

PKG='com.android.settings'


def choose(a,field,text):
    focus(a,field,expected_package=PKG);a.key('a')
    for _ in range(40):
        _,root,_,state=a.snap('conditional-network-chooser')
        if any(n.get('visible') and n.get('text')==text for n in descendants(root)):break
        a.key('d')
    else:raise RuntimeError('Exact chooser value not found: '+text)
    focus(a,text,expected_package=PKG);a.key('a')
    return a.snap('conditional-network-value-applied',True)[3]


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('conditional-network-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    result={'status':'RUNNING','settings_saved':False,'network_saved':False};a=Audit()
    try:
        dns='settings get global private_dns_mode; settings get global private_dns_specifier'
        result['dns_before']=adb(dns)
        enter_supplement(a,{'setup_action':'android.settings.WIRELESS_SETTINGS','path':['网络和互联网','私人 DNS']})
        focus(a,'private_dns_mode_provider',expected_package=PKG);a.key('a')
        focus(a,'private_dns_mode_provider_hostname',expected_package=PKG)
        for _ in range(6):
            data,root,_,_=a.snap('conditional-dns-ime-settle')
            if any(w.get('type')==2 for w in data['windows']):break
            time.sleep(.2)
        if not any(w.get('type')==2 for w in data['windows']):a.key('a')
        data,root,_,result['dns_keyboard']=a.snap('conditional-dns-tv-ime',True)
        if not any(w.get('type')==2 and w.get('root',{}).get('package')=='com.android.inputmethod.leanback' for w in data['windows']):
            raise RuntimeError('Private DNS field did not open TV IME')
        field=next(n for n in descendants(root) if n.get('id')==PKG+':id/private_dns_mode_provider_hostname')
        # Existing hostname is user data. Never replace or append to it.
        saved_specifier=[line.strip() for line in result['dns_before'].splitlines() if line.strip()][-1]
        if saved_specifier not in ('null',''):
            result['dns_existing_text_preserved']=True
        else:
            initial_hint=field.get('text','')
            def read_hostname(current_root):
                value=next(n.get('text','') for n in descendants(current_root)
                           if n.get('id')==PKG+':id/private_dns_mode_provider_hostname')
                return '' if value==initial_hint else value
            result['dns_typed']=type_ascii(a,'dns',read_hostname,'conditional-dns')
        a.key('b')
        value=graph(a,['条件网络表单',args.tag,'私人DNS已启用自定义主机名'],180)
        result['dns_graph']=value['status']
        if value['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('DNS graph not closed')
        signatures=[s.get('focus_signature') or '' for s in value['nodes'].values()]
        if not any('private_dns_mode_provider_hostname' in s for s in signatures):raise RuntimeError('DNS hostname not reached')
        focus(a,'button2',expected_package=PKG);a.key('a')
        result['dns_cancel']=a.snap('conditional-dns-actual-cancel',True)[3]
        result['dns_after']=adb(dns)
        if result['dns_after']!=result['dns_before']:raise RuntimeError('Private DNS settings changed')
        result['wifi_before']=adb('dumpsys wifi | grep mWifiInfo')
        enter_supplement(a,{'setup_action':'android.settings.WIFI_SETTINGS','path':['网络和互联网','WLAN','添加网络']})
        data,_,_,_=a.snap('conditional-tls-empty-form')
        if any(w.get('type')==2 for w in data['windows']):a.key('b')
        result['enterprise']=choose(a,'security','WPA/WPA2/WPA3-Enterprise')
        result['tls']=choose(a,'method','TLS')
        result['ca']=choose(a,'ca_cert','使用系统证书')
        top(a);seen=set();last=None;repeated=0;result['tls_states']=[]
        for _ in range(120):
            _,root,node,state=a.snap('conditional-tls-field-walk')
            if state['package']!=PKG or state['window']!='添加网络':raise RuntimeError('TLS walk left owned form')
            result['tls_states'].append(state)
            if node:seen.add(node.get('id'))
            boundary=(state['focus_signature'],tuple(state.get('focus_bounds') or []))
            repeated=repeated+1 if boundary==last else 0
            if repeated>=2:break
            last=boundary;a.key('d')
        else:raise RuntimeError('TLS semantic walk did not finish')
        required=['ssid','security','method','ca_cert','domain','user_cert','identity']
        result['tls_reached_ids']=sorted(x for x in seen if x)
        missing=[field for field in required if PKG+':id/'+field not in seen]
        if missing:raise RuntimeError('Missing TLS controls: '+repr(missing))
        focus(a,'user_cert',expected_package=PKG)
        before=a.snap('conditional-user-cert-before')[3];a.key('a')
        if a.snap('conditional-user-cert-open')[3]['window_id']==before['window_id']:
            raise RuntimeError('TLS client certificate chooser did not open')
        e=Explorer(a,args.tag+'-tls-user-cert');e.visit(['条件网络表单',args.tag,'TLS客户端证书选择'],True)
        result['client_certificate_scan']=e.output.name
        a.key('b');focus(a,'button2',expected_package=PKG);a.key('a')
        result['tls_cancel']=a.snap('conditional-tls-actual-cancel',True)[3]
        result['wifi_after']=adb('dumpsys wifi | grep mWifiInfo')
        if 'Xiaomi_0421' not in result['wifi_after'] or 'COMPLETED' not in result['wifi_after']:raise RuntimeError('Original Wi-Fi not connected')
        result['status']='PASS_CUSTOM_DNS_TV_FIELD_TLS_CLIENT_CERT_FIELDS_CHOOSER_CANCEL_NO_SAVE'
    except Exception as error:result.update(status='ERROR',error=repr(error));raise
    finally:
        a.close();output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(result['status'],flush=True)


if __name__=='__main__':main()
