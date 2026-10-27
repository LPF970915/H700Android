"""Repeat three actual D-pad WLAN cycles, retaining timing and network/ADB evidence."""
import argparse,json,re,time,subprocess
import audit
from audit import Audit,OUT,adb,descendants
from followup import enter,top

def main():
 p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--dwell',type=int,default=0);args=p.parse_args()
 if args.dwell<0 or args.dwell>90:raise ValueError('Dwell must be 0..90 seconds')
 if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
 receipt=OUT/('wifi-repeated-'+args.tag+'.json')
 if receipt.exists():raise ValueError('New evidence tag required')
 a=Audit();r={'status':'RUNNING','cycles':[],'dwell_seconds':args.dwell};baseline=None
 def save():receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
 try:
  baseline=adb('settings get global wifi_on').strip()
  if baseline!='1':raise RuntimeError('Expected initially enabled WLAN')
  enter(a,['网络和互联网','WLAN'])
  for number in range(1,4):
   top(a);a.key('d');_,root,node,state=a.snap('wifi-repeat-'+str(number)+'-before',True)
   master=next(n for n in descendants(root) if n.get('id','').endswith('/switch_bar'))
   allowed={master['id']}|{n['id'] for n in descendants(master) if n.get('checkable') and n.get('id')}
   if state['window']!='WLAN' or not node or node.get('id') not in allowed:raise RuntimeError('WLAN master not focused')
   item={'number':number,'before':state};r['cycles'].append(item);save()
   start=time.monotonic();a.key('a')
   for _ in range(15):
    status=a.command('dumpsys wifi | grep -E "Wi-Fi is|mWifiInfo"')
    if 'Wi-Fi is disabled' in status:break
    time.sleep(.5)
   else:raise RuntimeError('Controller did not disable WLAN')
   item.update(off_confirmed_s=round(time.monotonic()-start,2),off=status)
   selection=a.command('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
   selected=re.search(r'selectedId=([^\s]+)',selection)
   if 'mode=settings' not in selection or not selected or selected[1] not in allowed:raise RuntimeError('Disconnected master focus lost; refusing A')
   start=time.monotonic();a.key('a');deadline=start+180
   while time.monotonic()<deadline:
    status=a.command('dumpsys wifi | grep -E "Wi-Fi is|mWifiInfo"; ip -4 addr show wlan0 | grep "inet " || true')
    addresses=re.findall(r'(?:^|\n)\s*inet (192\.168\.31\.\d+)/',status)
    if 'SSID: Xiaomi_0421,' in status and 'Supplicant state: COMPLETED' in status and addresses:
     item.update(on_to_connected_upper_bound_s=round(time.monotonic()-start,2),connected=status)
     audit.TARGET=addresses[-1]+':5555';break
    time.sleep(1)
   else:raise RuntimeError('Saved SSID did not reconnect within 180 seconds')
   item['adb_read_retries']=[];identity_deadline=time.monotonic()+45
   while True:
    try:
     item['adb_identity']=adb('id; getprop ro.serialno')
     if audit.SERIAL not in item['adb_identity']:raise RuntimeError('Unexpected reconnected device')
     break
    except (subprocess.SubprocessError,TimeoutError) as error:
     item['adb_read_retries'].append(repr(error))
     if time.monotonic()>=identity_deadline:raise
     # Only this read is retried; no Wi-Fi action or controller key is replayed.
     time.sleep(.5)
   item['guards']=adb('iptables -C INPUT -p tcp --dport 5555 ! -s 192.168.31.211 -j DROP && ip6tables -C INPUT -p tcp --dport 5555 -j DROP && echo GUARDS_PRESENT')
   if 'GUARDS_PRESENT' not in item['guards']:raise RuntimeError('Debug guards lost')
   if args.dwell:
    deadline=time.monotonic()+args.dwell
    while time.monotonic()<deadline:time.sleep(min(5,max(0,deadline-time.monotonic())))
    full=adb('dumpsys wifi');name='wifi-repeat-'+args.tag+'-cycle-'+str(number)+'.txt'
    (OUT/name).write_text(full,encoding='utf8');item['settled_wifi_dump']=name
    config=full.split('SSID: "Xiaomi_0421"',1)[-1][:5000]
    state=re.search(r'NetworkSelectionStatus (NETWORK_SELECTION_[A-Z_]+)',config)
    count=re.search(r'numNoInternetAccessReports (\d+)',config)
    item['settled_network_selection']=state[1] if state else None
    item['no_internet_reports']=int(count[1]) if count else None
    current=adb('dumpsys wifi | grep mWifiInfo')
    if 'SSID: Xiaomi_0421,' not in current or 'Supplicant state: COMPLETED' not in current:raise RuntimeError('WLAN lost during validation dwell')
    if item['settled_network_selection']!='NETWORK_SELECTION_ENABLED':raise RuntimeError('Saved WLAN was disabled after validation')
   item['after']=a.snap('wifi-repeat-'+str(number)+'-after',True)[3];item['status']='PASS';save()
   print('WIFI_CYCLE_PASS',number,item['on_to_connected_upper_bound_s'],flush=True)
  r['wan_failure_policy_exercised']=any((i.get('no_internet_reports') or 0)>0 for i in r['cycles'])
  if args.dwell:
   r['local_wlan_policy_log']=adb('logcat -b all -d -v threadtime | grep -F "RGSP: keep local WLAN eligible after WAN validation failure" | tail -n 12')
   r['wan_failure_policy_exercised']=r['wan_failure_policy_exercised'] and 'RGSP: keep local WLAN eligible' in r['local_wlan_policy_log']
   if not r['wan_failure_policy_exercised']:raise RuntimeError('Three cycles passed, but WAN-failure policy was not exercised')
  r['status']='PASS_THREE_CONTROLLER_WIFI_CYCLES_RECONNECTED_AND_GUARDED_ADB';print(r['status'],flush=True)
 except Exception as e:
  r.update(status='ERROR',error=repr(e))
  if baseline=='1':r['recovery']=a.command('svc wifi enable; sh /data/local/tmp/rgsp-restore-debug.sh')
  raise
 finally:a.close();save()
if __name__=='__main__':main()
