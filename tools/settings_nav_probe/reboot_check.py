"""Reboot once under UART observation, then explicitly restore guarded temporary ADB."""
import argparse
import datetime
import json
import re
import time
from audit import Audit, OUT, adb, label, descendants
from power_input import open_power_menu


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--via-power-menu',action='store_true',help='Confirm the native Restart action with physical controller A')
    parser.add_argument('--uart',action='store_true',help='Observe the menu and initial identity without Wi-Fi ADB')
    args=parser.parse_args()
    if not args.execute: parser.error('Explicit --execute required; this reboots the device once')
    stamp=datetime.datetime.now().strftime('%H%M%S')
    result={'kind':'software_reboot','status':'STARTING','physical_cold_boot':False}
    if args.via_power_menu:result['kind']='controller_power_menu_restart'
    receipt=OUT/('reboot-'+stamp+'.json')
    serial_log=OUT/('reboot-'+stamp+'.uart.log')
    a=Audit()
    if args.uart:a.observation_transport='uart'
    try:
        if args.uart:
            raw=a.command('cat /proc/sys/kernel/random/boot_id')
            ids=re.findall(r'(?m)^([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\r?$',raw)
            if len(ids)!=1:raise RuntimeError('Ambiguous boot identity')
            before=ids[0]
        else:before=adb('cat /proc/sys/kernel/random/boot_id').strip()
        result['boot_id_before']=before
        a.command('test -f /data/local/tmp/rgsp-restore-debug.sh && sync')
        if args.via_power_menu:
            a.key('wake')
            _,root,_,result['awake_before_menu']=a.snap('power-restart-awake',True)
            if any('global_actions' in n.get('id','') for n in descendants(root)):
                raise RuntimeError('Power menu was already open; refusing an ambiguous A')
            if result['awake_before_menu']['package']=='com.android.systemui':
                a.key('a')
                result['a_unlock_before_menu']=a.snap('power-restart-a-unlock',True)[3]
            result['opening']='Verified axp2202-pek evdev KEY_POWER hold/release; no synthetic LONG_PRESS flag'
            result['open_power_menu']=open_power_menu(a)
            for _ in range(12):
                _,root,_,state=a.snap('power-restart-menu-settle',True)
                if state['package']=='com.android.systemui' and any('global_actions' in n.get('id','') for n in descendants(root)):break
                time.sleep(.25)
            else:raise RuntimeError('Native global actions window did not appear after actual power hold')
            for index in range(32):
                _,root,node,state=a.snap('power-restart-confirm-focus',True)
                if state['package']!='com.android.systemui' or not any('global_actions' in n.get('id','') for n in descendants(root)):
                    raise RuntimeError('Restart requires the native global actions window')
                if node and node.get('clickable') and label(node) in ('重新启动','重启'):
                    result['restart_focus']=state;break
                a.key(('d','r','u','l')[index%4])
            else:raise RuntimeError('Native Restart action not reachable; no A injected')
        a.port.read_all()
        # Begin observing immediately so the full boot log is retained even if
        # Android restarts before a framed shell command could return.
        a.port.write(b'sh /data/local/tmp/nav-hat.sh a 0.12\r' if args.via_power_menu else b'reboot\r'); a.port.flush()
        print('REBOOT_SENT',flush=True)
        deadline=time.monotonic()+240
        next_query=time.monotonic()+20
        console_seen=False
        kernel_seen=False
        recent=b''
        with serial_log.open('wb') as log:
            while time.monotonic()<deadline:
                chunk=a.port.read(8192)
                if chunk:
                    log.write(chunk);log.flush()
                    recent=(recent+chunk)[-16000:]
                    # Never type into a bootloader countdown or a failed boot.
                    kernel_seen |= b'Linux version' in chunk or b'Starting kernel' in chunk
                    console_seen |= kernel_seen and bool(re.search(rb'rgsp:/[^\r\n]*#',chunk))
                    states=re.findall(rb'(?:^|\n)RGSP_BOOT:([^:\r\n]*):([^:\r\n]*):([a-f0-9-]+)\r?',recent)
                    for serial,complete,boot in states:
                        if serial==b'5c001089d750c872012' and complete==b'1' and boot.decode()!=before:
                            result['boot_id_after']=boot.decode()
                            result['status']='BOOT_COMPLETED'
                            break
                    if result['status']=='BOOT_COMPLETED':break
                if console_seen and time.monotonic()>=next_query:
                    a.port.write(b'echo RGSP_BOOT:$(getprop ro.serialno):$(getprop sys.boot_completed):$(cat /proc/sys/kernel/random/boot_id)\r')
                    a.port.flush();next_query=time.monotonic()+10
                    print('WAITING_FOR_NEW_BOOT',flush=True)
            else:raise RuntimeError('New Android boot did not complete within 240 seconds; no automatic rollback attempted')
        result['before_transport_restore']=a.command(
            "echo BOOT_SERVICE_PORT=$(getprop service.adb.tcp.port); "
            "echo BOOT_PERSISTENT_PORT=$(getprop persist.adb.tcp.port); "
            "if awk '$2 ~ /:15B3$/ && $4 == \"0A\" {found=1} END {exit !found}' "
            "/proc/net/tcp /proc/net/tcp6; then echo BOOT_TCP_LISTENING=1; "
            "else echo BOOT_TCP_LISTENING=0; fi")
        result['no_implicit_listener']=bool(re.search(
            r'(?:^|\n)BOOT_TCP_LISTENING=0\r?(?:\r?\n|$)',result['before_transport_restore']))
        result['uart_restore']=a.command('sh /data/local/tmp/rgsp-restore-debug.sh',timeout=30)
        if not result['no_implicit_listener']:
            raise RuntimeError('Unexpected TCP 5555 listener before explicit guard restore')
        result['status']='BOOT_COMPLETED_GUARDED_TRANSPORT_RESTORED'
        print(result['status'],flush=True)
    except Exception as error:
        result['error']=repr(error)
        raise
    finally:
        a.close()
        receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
