"""UART-only navigation with a passive, non-suppressing hierarchy probe over ADB."""
import argparse
import base64
import gzip
import zlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
import serial
from probe_config import PROBE_DIR,PROBE_JAR,PROBE_SHA

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'out/settings-deep-audit-20261023'
ADB = str(Path(os.environ['LOCALAPPDATA'])/'Android/Sdk/platform-tools/adb.exe')
TARGET = '192.168.31.161:5555'
SERIAL = '5c001089d750c872012'

def completion_pattern(token):
    # The echoed command contains a literal $navrc, never a numeric result.
    # Kernel console output can be inserted before/after the real numeric marker.
    return re.compile(re.escape(token.encode())+rb':(\d+)(?=\r|\n|\[|$)')

def adb(command, timeout=20):
    # Keep the server in this long-running audit's process tree. Reconnect before
    # an operation when necessary; never replay an operation after it has begun.
    state=subprocess.run([ADB,'-s',TARGET,'get-state'],capture_output=True,timeout=10)
    if state.returncode or state.stdout.strip()!=b'device':
        subprocess.run([ADB,'start-server'],check=True,capture_output=True,timeout=15)
        subprocess.run([ADB,'connect',TARGET],check=True,capture_output=True,timeout=15)
        deadline=time.monotonic()+8
        while True:
            state=subprocess.run([ADB,'-s',TARGET,'get-state'],capture_output=True,timeout=10)
            if state.returncode==0 and state.stdout.strip()==b'device': break
            if time.monotonic()>=deadline: raise RuntimeError('ADB transport unavailable: '+TARGET)
            time.sleep(.3)
        identity=subprocess.check_output([ADB,'-s',TARGET,'shell','getprop ro.serialno'],timeout=10)
        if identity.decode().strip()!=SERIAL: raise RuntimeError('Reconnected ADB target is a different device')
    return subprocess.check_output([ADB,'-s',TARGET,'shell',command],timeout=timeout).decode('utf-8',errors='replace')

def descendants(node):
    yield node
    for child in node.get('children',[]):
        yield from descendants(child)

def label(node):
    if node.get('ownerLabel'): return node['ownerLabel']
    # Recent-app cards carry a changing "N minutes ago" summary. The app title
    # alone identifies the control; time text must not create new page templates.
    if re.fullmatch(r'com\.android\.settings:id/app[123]_view',node.get('id','')):
        names=[n.get('text') for n in descendants(node)
               if n.get('id')=='com.android.settings:id/app_title' and n.get('text')]
        if len(names)==1:return names[0]
    # Preference summary text is deliberately excluded from stable control identifiers.
    titles=[n.get('text','') for n in descendants(node)
            if n.get('id') in ('android:id/title','com.android.settings:id/title') and n.get('text')]
    if titles: return titles[0]
    own=node.get('text') or node.get('desc')
    if own: return own
    texts=[n.get('text','') for n in descendants(node) if n.get('text')]
    return ' / '.join(texts[:2]) or node.get('id') or node.get('class','')

def signature(node):
    item=node.get('collection') or node.get('ownerCollection')
    position=('|row='+str(item.get('row'))+',column='+str(item.get('column'))) if item else ''
    return '|'.join([label(node),node.get('id',''),node.get('class','')])+position

def viewport(root):
    return tuple((n.get('id'),n.get('text'),tuple(n.get('bounds',[])))
        for n in descendants(root) if n.get('visible') and n.get('id','').endswith('/title'))

def owner_metadata(root, target):
    """Name repeated row widgets by their actual owning row, not only 'On'."""
    def path(node, parents):
        if (node.get('bounds')==target.get('bounds') and node.get('id')==target.get('id')
                and node.get('class')==target.get('class')): return parents
        for child in node.get('children',[]):
            found=path(child,parents+[node])
            if found is not None: return found
        return None
    parents=list(reversed(path(root,[]) or []))
    collection=target.get('collection') or next((p['collection'] for p in parents if p.get('collection')),None)
    for parent in parents:
        titles=[n.get('text') for n in descendants(parent)
            if n.get('id','').endswith('/title') and n.get('text')]
        if len(titles)==1: return titles[0],collection
        texts=[n.get('text') for n in descendants(parent) if n.get('text')
            and not (n.get('editable') or n.get('checkable') or n.get('range'))
            and not n.get('id','').endswith('/summary')]
        if texts: return ' / '.join(dict.fromkeys(texts[:2])),collection
    return '',collection

def decode_uart_probe(output, token):
    start=re.search(r'^NVBEGIN_'+re.escape(token)+r'\r?$',output,re.M)
    end=re.search(r'^NVEND_'+re.escape(token)+r'\r?$',output,re.M)
    if not start or not end or end.start()<=start.end():raise ValueError('UART probe frame missing')
    body=output[start.end():end.start()]
    digest=re.search(r'^([a-f0-9]{64})  /data/local/tmp/nav-passive-audit/response\r?$',body,re.M)
    if not digest:raise ValueError('UART probe checksum missing')
    encoded=''.join(line.strip() for line in body[:digest.start()].splitlines()
                    if re.fullmatch(r'[A-Za-z0-9+/=]+',line.strip()))
    raw=base64.b64decode(encoded,validate=True)
    if raw.startswith(b'\x1f\x8b'):
        try:raw=gzip.decompress(raw)
        except (OSError,EOFError,zlib.error) as error:raise ValueError('Corrupt compressed UART probe') from error
    if hashlib.sha256(raw).hexdigest()!=digest[1]:raise ValueError('UART probe checksum mismatch')
    envelope=json.loads(raw)
    if envelope['token']!=token:raise ValueError('UART passive probe response is stale')
    return envelope['snapshot']


class Audit:
    def __init__(self):
        OUT.mkdir(parents=True,exist_ok=True)
        self.control_transport=os.environ.get('NAV_CONTROL_TRANSPORT','uart')
        if self.control_transport not in ('uart','adb'):raise ValueError('Unknown control transport')
        self.port=None
        if self.control_transport=='uart':
            self.port=serial.Serial('COM4',115200,timeout=.05,write_timeout=2,xonxoff=False,rtscts=False,dsrdtr=False)
            self.port.dtr=False; self.port.rts=False
        self.counter=0
        self.navigation_version=None
        self.observation_transport="adb"
        self.probe_identity_checked=False
        try:
            self.command('test "$(getprop ro.serialno)" = '+SERIAL)
            self.command('n() { sh /data/local/tmp/nav-hat.sh "$1"; }')
        except Exception:
            self.close()
            raise

    def close(self):
        if self.port:self.port.close()

    def ensure_probe(self):
        """Start only after the previous observer exits; never replay an input."""
        read=self.command if self.observation_transport=='uart' else adb
        query=("ps -A -o PID,ARGS | awk '$2==\"app_process\" && $3==\"/system/bin\" "
               "&& $4==\"Dump\" && $5==\"--daemon\" {print \"NVPROBE_PID:\"$1}'; "
               'if [ -f '+PROBE_DIR+'/ready ]; then echo NVPROBE_READY:1; else echo NVPROBE_READY:0; fi')
        for attempt in range(8):
            status=read(query)
            alive=bool(re.search(r'^NVPROBE_PID:[0-9]+\r?$',status,re.M))
            ready=bool(re.search(r'^NVPROBE_READY:1\r?$',status,re.M))
            if alive and ready:return False
            if not alive:break
            time.sleep(.15)
        else:raise RuntimeError('Previous passive observer is alive but not ready; no replacement started')
        previous=read('cat '+PROBE_DIR+'/log 2>/dev/null || true')
        self.command('test "$(sha256sum '+PROBE_JAR+' | cut -d \' \' -f 1)" = '+PROBE_SHA)
        self.command('rm -f '+PROBE_DIR+'/request '+PROBE_DIR+'/request.next '+PROBE_DIR+'/response '+PROBE_DIR+'/stop '+PROBE_DIR+'/ready')
        self.command('nohup sh -c "CLASSPATH='+PROBE_JAR+' app_process /system/bin Dump --daemon '+PROBE_DIR+'" > '+PROBE_DIR+'/log 2>&1 < /dev/null & true')
        for _ in range(30):
            if re.search(r'^NVPROBE_READY:1\r?$',read(query),re.M):break
            time.sleep(.15)
        else:raise RuntimeError('New bounded passive observer did not become ready')
        with (OUT/'probe-rotation-events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'time':datetime.datetime.now().isoformat(),'previous_log':previous,
                'jar_sha256':PROBE_SHA,'keys_replayed':False},ensure_ascii=False)+'\n')
        return True

    def command(self, command, timeout=30):
        if self.control_transport=='adb':
            # Explicit fallback when the host UART driver is unavailable. The
            # same nav-hat.sh sends real event-node HAT/A/B inputs. Never retry
            # a command after execution has begun.
            output=adb('n() { sh /data/local/tmp/nav-hat.sh "$1"; }; '+command,timeout=timeout)
            with (OUT/'adb-control.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps({'command':command,'output':output,
                    'transport':'adb','keys_replayed':False},ensure_ascii=False)+'\n')
            return output
        token='NV'+uuid.uuid4().hex[:8]
        wire=command+'; navrc=$?; echo '+token+':$navrc'
        # Match the numeric result, not the echoed command's literal $navrc.
        self.port.read_all()
        # Clear any stray bytes left in the interactive Android shell's input
        # line after console noise. Never replay a completed mutating command.
        self.port.write(b'\x15')
        self.port.flush()
        for byte in (wire+'\r').encode():
            self.port.write(bytes([byte])); time.sleep(.008)
        data=bytearray(); deadline=time.monotonic()+timeout
        pattern=completion_pattern(token)
        while time.monotonic()<deadline:
            data.extend(self.port.read(8192))
            found=pattern.search(data)
            if found: break
        else:
            raise RuntimeError('UART completion missing: '+repr(data[-1000:]))
        with (OUT/'uart.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'command':command,'rc':int(found[1]),'output':data.decode('utf-8',errors='replace')},ensure_ascii=False)+'\n')
        if int(found[1]): raise RuntimeError('UART command failed: '+command)
        return data.decode('utf-8',errors='replace')

    def key(self, key):
        if (OUT/'STOP_AUDIT').exists(): raise RuntimeError('Key injection stopped by STOP_AUDIT')
        allowed={'u':'up','d':'down','l':'left','r':'right','a':'a','b':'b','home':'home','select':'select'}
        if key in allowed: self.command('n '+allowed[key])
        elif key=='wake':
            # The swipe keyguard overrides the normal 30-minute timeout with
            # 10 seconds. Warm the passive observer before starting that clock.
            self.ensure_probe()
            # Injected WAKEUP can leave this BSP in a noninteractive state.
            # A short POWER press is safe only after checking it is asleep.
            state=self.command('dumpsys power | grep -E "mWakefulness=|Display Power:"')
            if re.search(r'mWakefulness=(Asleep|Dozing)\b',state):
                self.command('input keyevent 26')
            elif 'mWakefulness=Dreaming' in state:
                self.command('input keyevent 224')
            elif 'mWakefulness=Awake' not in state:
                raise RuntimeError('Unknown power state; no POWER toggle injected')
            for _ in range(10):
                power=self.command('dumpsys power | grep -E "mWakefulness=|Display Power:"')
                ui=self.command('dumpsys activity service com.android.systemui/.SystemUIService | grep mDeviceInteractive:')
                if ('mWakefulness=Awake' in power and 'Display Power: state=ON' in power
                        and re.search(r'^\s*mDeviceInteractive: true\s*$',ui,re.M)):
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('Display/SystemUI did not finish waking; no follow-up A injected')
        else: raise ValueError(key)
        time.sleep(.15 if key in 'udlr' else .65)

    def snap(self, tag='state', screenshot=False):
        uart = self.observation_transport == "uart"
        self.ensure_probe()
        if not uart and not self.probe_identity_checked:
            if adb('getprop ro.serialno').strip()!=SERIAL:
                raise RuntimeError('Passive ADB probe does not match the UART device')
            self.probe_identity_checked=True
        self.counter+=1
        stamp=datetime.datetime.now().strftime('%H%M%S_%f')
        stem=re.sub('[^a-zA-Z0-9_.-]','_',tag)[:65]+'-'+stamp
        remote='/data/local/tmp/nav-probe-'+stamp+'.json'
        if uart:
            for attempt in range(3):
                token=uuid.uuid4().hex[:16]
                directory='/data/local/tmp/nav-passive-audit'
                output=self.command(f'd={directory}; test -f "$d/ready" && rm -f "$d/response" && '
                    f'echo {token} > "$d/request.next" && mv "$d/request.next" "$d/request"; pw=0; while [ ! -f "$d/response" ] && [ "$pw" -lt 100 ]; '
                    'do sleep 0.05; pw=$((pw+1)); done; '
                    f'echo NVBEGIN_{token}; gzip -c "$d/response" | base64; sha256sum "$d/response"; echo NVEND_{token}',timeout=45)
                try:
                    data=decode_uart_probe(output,token);break
                except (ValueError,KeyError):
                    if attempt==2:raise
                    # Repeat only passive observation after transport corruption;
                    # never replay the preceding controller action.
        else:
            daemon=os.environ.get('NAV_PROBE_DAEMON') or '/data/local/tmp/nav-passive-audit'
            if daemon!='/data/local/tmp/nav-passive-audit': raise ValueError('Unexpected daemon directory')
            for attempt in range(3):
                # The bounded observer can retire between ensure_probe's ready
                # check and this passive request. Rotate/reobserve, never replay
                # the controller action which preceded this snapshot.
                if attempt:self.ensure_probe()
                token=uuid.uuid4().hex[:16]
                try:
                    # Publish a complete token atomically. Truncating the live
                    # request lets the strict observer occasionally read empty.
                    output=adb(f'test -f {daemon}/ready && rm -f {daemon}/response && echo {token} > {daemon}/request.next && mv {daemon}/request.next {daemon}/request; '
                        f'nav_wait=0; while [ ! -f {daemon}/response ] && [ "$nav_wait" -lt 100 ]; do sleep 0.05; nav_wait=$((nav_wait+1)); done; cat {daemon}/response')
                    envelope=json.loads(output[output.index('{'):])
                    if envelope['token']!=token: raise ValueError('Passive probe response is stale')
                    data=envelope['snapshot'];break
                except (subprocess.SubprocessError,ValueError,KeyError) as error:
                    with (OUT/'passive-read-retries.jsonl').open('a',encoding='utf8') as f:
                        f.write(json.dumps({'time':datetime.datetime.now().isoformat(),'attempt':attempt+1,
                            'error':repr(error),'keys_replayed':False})+'\n')
                    if attempt==2:raise
                    time.sleep(.3)
        (OUT/(stem+'.json')).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        windows=[w for w in data['windows'] if w.get('type')==1 and w.get('root')]
        focused=[w for w in data['windows'] if w.get('type') in (1,3) and w.get('focused') and w.get('root')]
        active=focused[0] if focused else (windows[0] if windows else {})
        root=active.get('root',{})
        focus=next((n for n in descendants(root) if n.get('focused')),None)
        # AdapterView keeps input focus on the list, while the actionable row is
        # exposed as selected. Use that row so long choice lists are not mistaken
        # for an unmoving focus after three Down presses.
        if focus and focus.get('class') in ('android.widget.ListView','android.widget.GridView'):
            selected=[n for n in descendants(focus) if n is not focus and n.get('visible') and n.get('selected')]
            actionable=next((n for n in selected if n.get('clickable')),None)
            if actionable is None: actionable=next((n for n in selected if n.get('text')),None)
            if actionable: focus=dict(actionable,adapterSelected=True)
        overlay_focused=any(w.get('type')==4 and w.get('focused') for w in data['windows'])
        if (focus is None or overlay_focused) and root.get('package') in ('com.android.settings','com.android.settings.intelligence','com.android.documentsui','com.android.permissioncontroller','com.android.inputmethod.latin','com.android.providers.media'):
            service=(self.command if uart else adb)('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
            implementation=re.search(r'navigationVersion=(\d+)',service)
            if implementation: self.navigation_version=int(implementation[1])
            selected=re.search(r'selectedBounds=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]',service)
            if selected:
                bounds=[int(x) for x in selected.groups()]
                matches=[n for n in descendants(root) if n.get('bounds')==bounds and n.get('visible')]
                focus=next((n for n in matches if n.get('clickable') or n.get('editable') or n.get('range')),matches[0] if matches else None)
                if focus: focus=dict(focus,helperSelected=True)
        if focus:
            owner,collection=owner_metadata(root,focus)
            if collection: focus=dict(focus,ownerCollection=collection)
            if owner and ('Switch' in focus.get('class','') or (focus.get('checkable') and not focus.get('text'))):
                focus=dict(focus,ownerLabel=owner)
        summary={'file':stem+'.json','window':active.get('title',''), 'window_id':active.get('id'), 'package':root.get('package',''),
                 'navigation_version':self.navigation_version,
                 'focus':label(focus) if focus else None,'focus_signature':signature(focus) if focus else None,
                 'focus_bounds':focus.get('bounds') if focus else None}
        if screenshot and uart:
            summary['screenshot_unavailable']='ADB intentionally disabled; raw passive UART hierarchy saved'
        if screenshot and not uart:
            adb('screencap -p /data/local/tmp/nav-deep.png')
            subprocess.run([ADB,'-s',TARGET,'pull','/data/local/tmp/nav-deep.png',str(OUT/(stem+'.png'))],check=True,capture_output=True)
            summary['screenshot']=stem+'.png'
        with (OUT/'states.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(summary,ensure_ascii=False)+'\n')
        return data,root,focus,summary

    def hold(self,key):
        if (OUT/'STOP_AUDIT').exists(): raise RuntimeError('Key injection stopped by STOP_AUDIT')
        direction={'u':'up','d':'down','l':'left','r':'right'}[key]
        self.command('sh /data/local/tmp/nav-hat.sh '+direction+' 0.8')
        time.sleep(.2)

    def show(self,tag='show'):
        data,root,focus,summary=self.snap(tag,True)
        print(json.dumps(summary,ensure_ascii=False),flush=True)
        for n in descendants(root):
            if (n.get('clickable') or n.get('focusable') or n.get('scrollable')) and n.get('visible'):
                print(json.dumps({'label':label(n),'id':n.get('id'),'class':n.get('class'),
                    'bounds':n.get('bounds'),'focus':n.get('focused'),'enabled':n.get('enabled'),
                    'scroll':n.get('scrollable'),'checkable':n.get('checkable'),
                    'checked':n.get('checked')},ensure_ascii=False),flush=True)

    def seek(self,text,limit=100,*,actionable=False):
        seen={}
        for i in range(limit):
            _,root,focus,state=self.snap('seek')
            if focus and (label(focus)==text or text in label(focus)) and (
                    not actionable or (focus.get('clickable') and focus.get('enabled'))):
                if not focus.get('clickable') and focus.get('class') in ('androidx.recyclerview.widget.RecyclerView','android.widget.ListView'):
                    # A container's concatenated label is not its first row. Move
                    # down/up to obtain a real actionable item before confirming.
                    self.key('d'); self.key('u')
                    _,root,focus,state=self.snap('seek-container-row')
                    if not focus or not focus.get('clickable') or not (label(focus)==text or text in label(focus)):
                        self.key('d'); continue
                print('FOCUSED '+text,flush=True); return
            key=(state['focus_signature'],viewport(root)); seen[key]=seen.get(key,0)+1
            if seen[key]>3: raise RuntimeError('Focus repeated before target '+text+': '+str(state))
            self.key('d')
        raise RuntimeError('Target not reached: '+text)

    def walk(self,tag,limit=170):
        visited={}; visible={}; path=[]; repeat=0
        for i in range(limit):
            _,root,focus,state=self.snap(tag+'-walk',screenshot=(i==0))
            for n in descendants(root):
                if n.get('visible') and (n.get('focusable') or n.get('clickable')):
                    visible[signature(n)]={'label':label(n),'enabled':n.get('enabled'),'focusable':n.get('focusable'),'clickable':n.get('clickable')}
            sig=state['focus_signature']; path.append(state)
            if sig: visited[sig]=state
            print(json.dumps({'walk':tag,'step':i,'focus':state['focus']},ensure_ascii=False),flush=True)
            if len(path)>1 and sig==path[-2]['focus_signature']: repeat+=1
            else: repeat=0
            if repeat>=2: break
            self.key('d')
        else: raise RuntimeError('Walk step limit reached: '+tag)
        result={'tag':tag,'visited':visited,'visible_candidates':visible,'path':path}
        (OUT/(re.sub('[^a-zA-Z0-9_.-]','_',tag)+'-walk.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        self.snap(tag+'-end',True)
        return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['show','keys','seek','walk'])
    parser.add_argument('values',nargs='*')
    args=parser.parse_args(); a=Audit()
    try:
        if args.action=='show': a.show(args.values[0] if args.values else 'show')
        elif args.action=='keys':
            for key in args.values: a.key(key)
            a.show('after-keys')
        elif args.action=='seek': a.seek(' '.join(args.values)); a.show('target')
        elif args.action=='walk': a.walk(args.values[0])
    finally: a.close()

if __name__=='__main__': main()
