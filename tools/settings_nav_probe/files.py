"""Controller-only DocumentsUI audit helpers; all mutations use an owned fixture."""
import argparse
import json
import time
from audit import Audit, OUT, adb, descendants, label, signature, viewport
from graph import graph

PACKAGE='com.android.documentsui'
FIXTURE='/storage/emulated/0/Download/DPAD_AUDIT_20261024'


def visible_actions(root):
    return [n for n in descendants(root) if n.get('visible') and
            (n.get('clickable') or n.get('editable') or n.get('actions',0)&16
             or n.get('id','').endswith('/item_root'))]


def focus(a,text,limit=120,expected_package=PACKAGE):
    """Find a real semantic target through HAT, including horizontal toolbars."""
    _,root,node,state=a.snap('files-find-start')
    def matches(n):
        return n and (label(n)==text or n.get('desc')==text or n.get('id','').endswith('/'+text)
                or any(c.get('text')==text for c in descendants(n)))
    def position_key(root,node):
        # Scrolling can preserve the selected row while revealing new peers.
        # Its next directional edge must be explored in the new viewport.
        choices=tuple((signature(n),tuple(n.get('bounds',[]))) for n in visible_actions(root))
        return (signature(node) if node else '[NONE]',viewport(root),choices)
    drawer=any(n.get('visible') and n.get('id','').endswith('/drawer_roots')
               and n.get('bounds',[0,0,0,0])[0]>=0 and n.get('bounds',[0,0,0,0])[2]>100 for n in descendants(root))
    root_name=text in {'最近','图片','视频','音频','下载','RGSP H700','ROMS','错误报告','系统跟踪记录'}
    if state['window']=='弹出式窗口' or (drawer and root_name):
        origin=state['window_id']
        for direction in ('d','u'):
            previous=None;repeated=0
            for _ in range(45):
                if matches(node):return state
                now=state['focus_signature']
                repeated=repeated+1 if now==previous else 0
                if repeated>=2:break
                previous=now;a.key(direction);_,root,node,state=a.snap('files-menu-find-'+direction)
                if state['window_id']!=origin:raise RuntimeError('Direction left the popup menu')
    # A visible target usually needs only one or two ordinary direction edges.
    # Bounds choose the direction; confirmation still requires its exact semantics.
    attempted=set()
    for _ in range(18):
        if matches(node):return state
        candidates=[n for n in visible_actions(root) if matches(n)]
        if not node or not candidates:break
        target=candidates[0];b=node['bounds'];t=target['bounds']
        dx=(t[0]+t[2]-b[0]-b[2])/2;dy=(t[1]+t[3]-b[1]-b[3])/2
        if abs(dy)>=abs(dx):key='d' if dy>0 else 'u'
        else:key='r' if dx>0 else 'l'
        edge=(position_key(root,node),key)
        if edge in attempted or (node.get('editable') and key in ('l','r')):break
        attempted.add(edge);a.key(key);_,root,node,state=a.snap('files-find-direct-'+key)
        if state['package']!=expected_package:raise RuntimeError('Left expected package during directional lookup: '+expected_package)
    # BFS replays only direction edges. Never confirm a search candidate.
    edges={}; current=position_key(root,node); nodes={current:state}
    from graph import shortest_pending
    for _ in range(limit):
        if matches(node):return state
        route=shortest_pending(current,nodes,edges)
        if route is None:break
        key=route[0] if route else next(k for k in ('u','d','l','r') if (current,k) not in edges)
        if node and (node.get('range') or node.get('editable')) and key in ('l','r'):
            edges[current,key]=current;continue
        a.key(key);_,root,node,state=a.snap('files-find-'+key)
        if state['package']!=expected_package:raise RuntimeError('Left expected package during directional search: '+expected_package)
        dest=position_key(root,node);edges[current,key]=dest;nodes[dest]=state;current=dest
    raise RuntimeError('DocumentsUI target unreachable: '+text)


def open_control(a,text):
    before=focus(a,text);a.key('a');after=a.snap('files-opened',True)[3]
    return {'target':text,'before':before,'after':after}


def enter_source(a,root_label='下载'):
    data,root,_,state=a.snap('files-source-start')
    if state['window']=='弹出式窗口':
        # Bringing an existing task forward preserves its open overflow menu.
        # Close this non-committing popup before looking for the drawer toolbar.
        old_window=state['window_id'];a.key('b')
        data,root,_,state=a.snap('files-source-close-popup')
        if state['window_id']==old_window:raise RuntimeError('Files overflow did not close')
    if any(w.get('type')==2 for w in data['windows']):
        a.key('b');_,root,_,_=a.snap('files-source-hide-ime')
    if any(n.get('visible') and n.get('id','').endswith('/action_mode_close_button') for n in descendants(root)):
        open_control(a,'action_mode_close_button');_,root,_,_=a.snap('files-source-selection-closed')
    if any(n.get('visible') and n.get('editable') and n.get('id','').endswith('/search_src_text') for n in descendants(root)):
        open_control(a,'收起');_,root,_,_=a.snap('files-source-search-closed')
    drawers=[n for n in descendants(root) if n.get('id','').endswith('/drawer_roots') and n.get('visible')
             and n.get('bounds',[0,0,0,0])[0]>=0 and n.get('bounds',[0,0,0,0])[2]>100]
    if not drawers:open_control(a,'显示根目录')
    open_control(a,root_label)
    if root_label!='下载':open_control(a,'Download')
    open_control(a,'DPAD_AUDIT_20261024')
    open_control(a,'source')
    state=a.snap('files-known-source',True)[3]
    if state['window']!='source':raise RuntimeError('Known fixture source not reached')
    return state


def select_file(a,name):
    _,root,_,_=a.snap('files-select-start')
    if any(n.get('visible') and n.get('id','').endswith('/action_mode_close_button') for n in descendants(root)):
        open_control(a,'action_mode_close_button')
    focus(a,name);a.command('sh /data/local/tmp/nav-hat.sh a 0.8');time.sleep(.35)
    _,root,_,state=a.snap('files-selected',True)
    if not any(n.get('visible') and n.get('id','').endswith('/action_mode_close_button') for n in descendants(root)):
        raise RuntimeError('Native selection did not open')
    return state


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--setup',action='store_true',help='Launch app only; not evidence of launcher reachability')
    p.add_argument('--show',action='store_true')
    p.add_argument('--graph',type=str)
    p.add_argument('--open',type=str)
    p.add_argument('--back',action='store_true')
    p.add_argument('--source',action='store_true',help='Navigate through real roots into the owned source')
    p.add_argument('--path',nargs='+',help='Open these real controls before --select and --open')
    p.add_argument('--root',default='下载',help='Storage root for --source; full filesystem uses RGSP H700')
    p.add_argument('--select',type=str,help='Select this fixture file using long A')
    args=p.parse_args();a=Audit()
    try:
        if args.setup:
            # Refuse to overwrite a preexisting directory, even an earlier fixture.
            if adb('if [ -e '+FIXTURE+' ]; then echo EXISTS; fi').strip()!='EXISTS':
                a.command('mkdir -p '+FIXTURE+'/source '+FIXTURE+'/destination')
                a.command('printf "RGSP controller fixture 20261024\\n" > '+FIXTURE+'/source/sample.txt')
            a.command('am start -n com.android.documentsui/.files.FilesActivity')
            for _ in range(20):
                if 'com.android.documentsui/' in adb('dumpsys activity activities | grep mResumedActivity'):break
                time.sleep(.2)
            else:raise RuntimeError('DocumentsUI failed to enter foreground')
            time.sleep(.5)
        if args.back:a.key('b')
        if args.source:print(json.dumps(enter_source(a,args.root),ensure_ascii=False),flush=True)
        for component in (args.path or []):print(json.dumps(open_control(a,component),ensure_ascii=False),flush=True)
        if args.select:print(json.dumps(select_file(a,args.select),ensure_ascii=False),flush=True)
        if args.open:print(json.dumps(open_control(a,args.open),ensure_ascii=False),flush=True)
        if args.graph:
            r=graph(a,['文件',args.graph],350)
            print('FILES_GRAPH '+r['status'],flush=True)
        if args.show:
            a.show('files-inspect')
            _,root,_,_=a.snap('files-advertised-actions')
            for n in visible_actions(root):
                print(json.dumps({k:n.get(k) for k in ('id','class','text','desc','clickable','longClickable','editable','actions','bounds')},ensure_ascii=False),flush=True)
    finally:a.close()


if __name__=='__main__':main()
