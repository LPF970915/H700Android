"""Inject bounded controller events into the disposable H700InputProbe activity.

Requires eng/root ADB, the explicitly identified RG34XXSP, Navigation v7,
H700InputProbe.apk and /data/local/tmp/rg34-dev/stick-motion.jar already installed.
No user app is targeted. Raw evidence stays in the explicit private output folder.
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--adb',required=True)
parser.add_argument('--session',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
parser.add_argument('--cycles',type=int,default=2,choices=range(1,21))
parser.add_argument('--execute',action='store_true',help='Allow controller injection into the test activity')
args=parser.parse_args()
serial=json.loads(args.session.read_text(encoding='utf-8'))['serial']
assert re.fullmatch(r'[A-Za-z0-9]+',serial),'Use the saved USB serial'
def adb(*parts):
    return subprocess.check_output([args.adb,'-s',serial,*map(str,parts)],timeout=40).decode('utf-8','replace').replace('\r','')
def shell(command): return adb('shell',command)
assert shell('getprop ro.serialno').strip()==serial
assert shell('getprop ro.product.device').strip()=='rgsp'
assert shell('getprop ro.product.model').strip() in ('RGSP H700','RGSP_H700')
assert shell('getprop persist.vendor.rgsp.input_profile').strip()=='rg34xxsp'
assert shell('id -u').strip()=='0','Raw event test requires the development root session'
nodes=shell('for d in /sys/class/input/event*; do printf "%s " "$d"; cat "$d/device/name"; done')
found=re.findall(r'^/sys/class/input/(event[0-9]+) ANBERNIC-keys$',nodes,re.M)
assert len(found)==1,'Controller enumeration is ambiguous'
NODE='/dev/input/'+found[0]
assert 'versionCode=7 ' in shell('dumpsys package com.roc.rgsp.navtrial'), 'Expected Navigation v7'
assert 'com.roc.rgsp.inputprobe' in shell('pm list packages com.roc.rgsp.inputprobe')
if not args.execute:
    print('IDENTITY_VERIFIED; pass --execute to run the fixture test')
    raise SystemExit(0)
OUT=args.out;OUT.mkdir(parents=True,exist_ok=True)
RUN=time.strftime('%Y%m%d-%H%M%S')
CYCLES=args.cycles
def ev(code,value): return f'sendevent {NODE} 1 {code} {value}; sendevent {NODE} 0 0 0'
def key(code,value): shell(ev(code,value))
def tap(code,hold=.08): shell(ev(code,1)+f'; sleep {hold}; '+ev(code,0))
def toggle(hold=2.15):
    tap(310,hold)
    time.sleep(.3) # UP is delivered before the overlay changes focus.
def state():
    value=shell('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
    (OUT/('mouse-'+RUN+'.private.txt')).write_text(value)
    return value
def active(): return 'mouseMode=true' in state()
def events():
    data=shell('cat /data/user/0/com.roc.rgsp.inputprobe/files/events.jsonl')
    (OUT/('pointer-events-'+RUN+'.private.jsonl')).write_text(data)
    return [json.loads(line) for line in data.splitlines() if line.strip()]
def ends(since): return [e for e in events()[since:] if e['type']=='touch' and e['action'] in [1,3]]
def note(text): print(text,flush=True)

shell('am force-stop com.roc.rgsp.inputprobe')
shell('am start -W -n com.roc.rgsp.inputprobe/.PointerProbe');time.sleep(.6)
assert 'com.roc.rgsp.inputprobe/.PointerProbe' in shell('dumpsys window windows'), 'Fixture window missing'
assert not active()
try:
    # Select below the threshold must reach the app with its original timing.
    for hold in [.08,.85,1.8]:
        at=len(events());tap(310,hold);time.sleep(.2)
        assert not active()
        pair=[e for e in events()[at:] if e['type']=='key' and e['key']==109]
        assert pair[0]['action']==0 and pair[-1]['action']==1,pair
        assert pair[0]['downTime']==pair[-1]['downTime'],pair
        assert pair[-1]['time']-pair[0]['time'] >= hold*1000-35,pair
    tap(311);assert not active()
    key(308,1);tap(310);key(308,0);assert not active()
    # Both orders of Select+Start suppress mouse activation, even after 2s.
    key(310,1);tap(311);time.sleep(2.1);key(310,0);time.sleep(.3);assert not active()
    key(311,1);tap(310,2.15);key(311,0);time.sleep(.3);assert not active()
    shell(ev(308,1)+'; '+ev(309,1)+'; '+ev(311,1)+'; sleep 0.1; '+ev(311,0)+'; '+ev(309,0)+'; '+ev(308,0))
    assert not active()
    note('PASS sub-2s Select timing, both Select+Start orders, old shoulder chord disabled')
    # A full Select pair reaches the app before activation. Holding alone
    # never moves focus early or repeats the toggle while still held.
    at=len(events());key(310,1);time.sleep(2.2);assert not active()
    key(310,0);time.sleep(.3);assert active()
    pair=[e for e in events()[at:] if e['type']=='key' and e['key']==109]
    assert pair[0]['action']==0 and pair[-1]['action']==1,pair
    assert pair[0]['downTime']==pair[-1]['downTime'],pair
    at=len(events());toggle();assert not active()
    assert not [e for e in events()[at:] if e['type']=='key' and e['key']==109], 'Mouse-owned Select leaked'
    for cycle in range(CYCLES):
        toggle();assert active(),cycle
        toggle();assert not active(),cycle
    note('PASS release-time activation, balanced Select pair and '+str(CYCLES)+' enter/exit cycles')
    toggle();assert active()
    at=len(events());tap(304);time.sleep(.5)
    assert any(e['action']==1 for e in ends(at))
    at=len(events());tap(304,.8);time.sleep(1.1)
    assert any(e['action']==1 and e['duration']>=750 for e in ends(at))
    note('PASS A click and stationary long press')
    at=len(events());key(307,1);time.sleep(.3)
    print(shell('CLASSPATH=/data/local/tmp/rg34-dev/stick-motion.jar app_process /system/bin StickMotion X 0.75'))
    key(307,0);time.sleep(.5)
    drag=ends(at)
    assert len(drag)==1 and drag[0]['action']==1 and abs(drag[0]['dx'])>20,drag
    note('PASS X continuous drag and release')
    at=len(events());key(307,1);time.sleep(.4);key(307,0);time.sleep(.4)
    stationary=ends(at)
    assert len(stationary)==1 and stationary[0]['action']==1 and stationary[0]['duration']>=300,stationary
    note('PASS stationary X hold/release (Android 10 empty-continuation regression)')
    at=len(events());key(306,1)
    shell(f'sendevent {NODE} 3 17 1; sendevent {NODE} 0 0 0; sleep 0.18; sendevent {NODE} 3 17 0; sendevent {NODE} 0 0 0')
    time.sleep(.7);key(306,0)
    swipe=ends(at)
    assert any(e['action']==1 and e['dy'] < -50 for e in swipe),swipe
    note('PASS Y + D-pad scroll')
    at=len(events());key(307,1);time.sleep(.25);tap(305);time.sleep(.5);key(307,0)
    assert not active()
    ended=ends(at)
    assert len(ended)==1 and ended[0]['action'] in [1,3],ended
    touch=events();downs=sum(e['type']=='touch' and e['action']==0 for e in touch)
    terminal=sum(e['type']=='touch' and e['action'] in [1,3] for e in touch)
    assert downs==terminal,(downs,terminal)
    note('PASS B exit during drag, no open touch contacts')
    assert 'rejected=0' in state(),state()
    result={'select_short_passthrough':True,'select_hold_ms':2000,'select_release_toggle':True,
            'select_start_chords_passthrough':True,'old_shoulder_chord_disabled':True,
            'select_toggle_cycles':CYCLES,'click':True,'long_press':True,
            'continuous_drag':True,'scroll':True,'exit_ends_touch':True,'touch_downs':downs,'touch_terminals':terminal}
    (OUT/'input-test-results.json').write_text(json.dumps(result,indent=2)+'\n')
finally:
    for code in [304,305,306,307,308,309,310,311]: key(code,0)
    if active(): tap(305)
