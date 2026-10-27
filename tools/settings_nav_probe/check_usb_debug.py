"""Exercise the actual USB-debug preference and its explicit enable confirmation."""
import argparse
import datetime
import json
import re
import time
import uuid
from audit import Audit, OUT, adb, descendants
from followup import enter

STATUS='echo ADB_ENABLED=$(settings get global adb_enabled); echo ADBD_STATE=$(getprop init.svc.adbd); echo USB_STATE=$(getprop sys.usb.state); echo USB_CONFIG=$(getprop sys.usb.config); echo TCP_PORT=$(getprop service.adb.tcp.port)'


def uart_nodes(a):
    token=uuid.uuid4().hex[:16]
    directory='/data/local/tmp/nav-passive-audit'
    command=(f'rm -f {directory}/response; echo {token} > {directory}/request; probe_wait=0; '
        f'while [ ! -f {directory}/response ] && [ "$probe_wait" -lt 100 ]; do '
        'sleep 0.05; probe_wait=$((probe_wait+1)); done; '
        f'grep -q \'"token":"{token}"\' {directory}/response && '
        f'grep -Eo \'"id":"[^"]*/(title|alertTitle|message|button[12]|checkbox|switch_widget)"[^}}]*\' {directory}/response')
    output=a.command(command)
    nodes=[]
    for line in output.splitlines():
        if not line.startswith('"id":'):continue
        try:nodes.append(json.loads('{'+line+'}'))
        except json.JSONDecodeError:continue
    if not nodes:raise RuntimeError('No fresh passive UART hierarchy summary')
    return nodes,output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default=datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));parser.add_argument('--current',action='store_true',help='Use an already verified developer options page');args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',args.tag):raise ValueError('Invalid evidence tag')
    a=Audit();result={};baseline=None
    try:
        baseline=adb('settings get global adb_enabled').strip()
        if baseline!='1':raise RuntimeError('Expected debugging initially enabled')
        if args.current:
            _,root,_,state=a.snap('usb-current-entry')
            if state['package']!='com.android.settings' or state['window']!='开发者选项':
                raise RuntimeError('Current page is not developer options')
        else:enter(a,['系统','开发者选项'])
        a.seek('USB 调试',actionable=True)
        result['before']=a.snap('usb-v15-before',True)[3]
        a.key('a')
        for _ in range(12):
            result['off_uart']=a.command(STATUS)
            if 'ADB_ENABLED=0' in result['off_uart'] and 'ADBD_STATE=stopped' in result['off_uart']:break
            time.sleep(.5)
        else:raise RuntimeError('Preference did not disable adb and stop adbd')
        # Observe the existing passive probe entirely through UART while the
        # official daemon is stopped; do not create an extra ADB transport.
        nodes,result['off_probe_uart']=uart_nodes(a)
        selection=a.command('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
        bounds=re.search(r'selectedBounds=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]',selection)
        title=next((n for n in nodes if n.get('text')=='USB 调试'),None)
        if not bounds or not title or 'mode=settings' not in selection:
            raise RuntimeError('USB debug focus was lost; refusing another A')
        selected=[int(value) for value in bounds.groups()]
        if not (selected[1]<title['bounds'][3] and title['bounds'][1]<selected[3]):
            raise RuntimeError('The selected row no longer owns the USB debug title')
        a.key('a');nodes,result['confirmation_uart']=uart_nodes(a)
        texts=' '.join(n.get('text','') for n in nodes)
        if 'USB' not in texts or '调试' not in texts:raise RuntimeError('Not the expected USB debug confirmation')
        for _ in range(5):
            selection=a.command('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
            positive=next((n for n in nodes if n.get('id')=='android:id/button1' and n.get('enabled')),None)
            if positive and 'selectedId=android:id/button1' in selection:break
            a.key('r')
        else:raise RuntimeError('Explicit USB debug positive button was not reached')
        result['positive']=positive;a.key('a')
        for _ in range(12):
            result['on_uart']=a.command(STATUS)
            if 'ADB_ENABLED=1' in result['on_uart'] and 'ADBD_STATE=running' in result['on_uart']:break
            time.sleep(.5)
        else:raise RuntimeError('Confirmed preference did not enable debugging')
        result['restore_debug_uart']=a.command('sh /data/local/tmp/rgsp-restore-debug.sh')
        result['after']=a.snap('usb-v15-after',True)[3]
        result['status']='UI_USB_DEBUG_OFF_ON_CONFIRMED_WITH_NATURAL_STOP_AND_EXPLICIT_DIALOG'
        result['physical_usb_enumeration_tested']=False
        print(result['status'],flush=True)
    except Exception as error:
        result['error']=repr(error)
        if baseline=='1':result['recovery_uart']=a.command('settings put global adb_enabled 1; sh /data/local/tmp/rgsp-restore-debug.sh')
        raise
    finally:
        a.close();(OUT/('usb-debug-'+args.tag+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
