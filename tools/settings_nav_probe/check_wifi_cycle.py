"""Time a real controller Wi-Fi off/on cycle, observing disconnection over UART."""
import argparse
import datetime
import json
import re
import time
import audit
from audit import Audit, OUT, adb, descendants
from followup import enter, top


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',args.tag):raise ValueError('Invalid evidence tag')
    a=Audit();result={};baseline=None
    try:
        baseline=adb('settings get global wifi_on').strip()
        if baseline!='1':raise RuntimeError('Expected Wi-Fi initially on; not changing an off baseline')
        enter(a,['网络和互联网','WLAN']);top(a);a.key('d')
        _,root,focus,result['before']=a.snap('wifi-cycle-before',True)
        master=next(n for n in descendants(root) if n.get('id','').endswith('/switch_bar'))
        allowed={master['id']}|{n['id'] for n in descendants(master) if n.get('checkable') and n.get('id')}
        if result['before']['window']!='WLAN' or focus.get('id') not in allowed:
            raise RuntimeError('Actual controller focus is not the WLAN master switch')
        start=time.monotonic();a.key('a')
        for _ in range(15):
            off=a.command('dumpsys wifi | grep -E "Wi-Fi is|mWifiInfo"')
            if 'Wi-Fi is disabled' in off:break
            time.sleep(.5)
        else:raise RuntimeError('Controller did not disable Wi-Fi')
        result['off_confirmed_s']=round(time.monotonic()-start,2);result['off_uart']=off
        selection=a.command('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        selected=re.search(r'selectedId=([^\s]+)',selection)
        if 'mode=settings' not in selection or not selected or selected[1] not in allowed:
            raise RuntimeError('WLAN master focus was lost while disconnected; refusing another A')
        start=time.monotonic();a.key('a')
        deadline=start+180
        while time.monotonic()<deadline:
            status=a.command('dumpsys wifi | grep -E "Wi-Fi is|mWifiInfo"; ip -4 addr show wlan0 | grep "inet " || true')
            addresses=re.findall(r'(?:^|\n)\s*inet (192\.168\.31\.\d+)/',status)
            if 'SSID: Xiaomi_0421,' in status and 'Supplicant state: COMPLETED' in status and addresses:
                result['on_to_connected_upper_bound_s']=round(time.monotonic()-start,2)
                audit.TARGET=addresses[-1]+':5555';result['connected_uart']=status;break
            time.sleep(1)
        else:raise RuntimeError('Original SSID did not reconnect within 180 seconds')
        result['adb_identity']=adb('id; getprop ro.serialno')
        result['guards']=adb('iptables -C INPUT -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP && ip6tables -C INPUT -p tcp --dport 5555 -j DROP && echo GUARDS_PRESENT')
        if 'GUARDS_PRESENT' not in result['guards']:raise RuntimeError('Debug guards were lost')
        result['after']=a.snap('wifi-cycle-after',True)[3]
        result['status']='CONTROLLER_WIFI_OFF_ON_RECONNECTED_AND_GUARDED_ADB_VERIFIED'
        print(result['status'],result['on_to_connected_upper_bound_s'],flush=True)
    except Exception as error:
        result['error']=repr(error)
        if baseline=='1':result['recovery_uart']=a.command('svc wifi enable; sh /data/local/tmp/rgsp-restore-debug.sh')
        raise
    finally:
        a.close();(OUT/('wifi-cycle-'+args.tag+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
