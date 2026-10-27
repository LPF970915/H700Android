"""Explore four-direction focus edges without confirming or touching a control."""
from collections import deque
import hashlib
import json
import time
from audit import OUT, descendants, label, signature, viewport

DIRECTIONS=('u','d','l','r')
OPPOSITE={'u':'d','d':'u','l':'r','r':'l'}

def ranges(root):
    values={}
    def walk(n,parents):
        if n.get('range'):
            title=''
            for parent in reversed(parents):
                titles=[x.get('text') for x in descendants(parent) if x.get('id','').endswith('/title') and x.get('text')]
                if len(titles)==1: title=titles[0]; break
            key='|'.join([title,n.get('id',''),n.get('class','')])
            values[key]=n['range']
        for child in n.get('children',[]): walk(child,parents+[n])
    walk(root,[])
    return values

def shortest_pending(start,nodes,edges):
    pending=deque([(start,[])])
    seen={start}
    while pending:
        node,path=pending.popleft()
        if any((node,key) not in edges for key in DIRECTIONS): return path
        for key in DIRECTIONS:
            target=edges.get((node,key))
            if target is not None and target not in seen:
                seen.add(target); pending.append((target,path+[key]))
    return None

def graph(a,path,limit=700,guard=None):
    tag='graph-'+hashlib.sha1('/'.join(path).encode()).hexdigest()[:10]
    record={'path':path,'nodes':{},'edges':[],'range_restores':[],'status':'RUNNING'}
    target=OUT/(tag+'.json')
    def save(): target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    _,root,focus,state=a.snap(tag+'-entry',True)
    record['entry']=state
    origin=(state['package'],state['window'])
    def key_for(root,state):
        candidates=sorted(set(signature(n) for n in descendants(root)
            if n.get('visible') and n.get('enabled') and
            (n.get('clickable') or n.get('editable') or n.get('range') or n.get('actions',0)&16) and
            not any(kind in n.get('class','') for kind in ('RecyclerView','ScrollView','ListView','ViewPager'))))
        # A plain text pane keeps the same semantic focus while scrolling.
        # Treat its visible text/geometry as state so one scroll cannot hide
        # an unvisited lower viewport behind a self-loop edge.
        panes=[n for n in descendants(root) if n.get('visible') and n.get('scrollable')
               and n.get('class','').endswith('ScrollView')]
        readable=tuple((n.get('id'),n.get('text'),tuple(n.get('bounds',[])))
            for pane in panes for n in descendants(pane)
            if n.get('visible') and n.get('text'))
        # Dialog radio buttons can share an empty label and resource ID. Their
        # actual focused rectangle must distinguish them in the direction graph.
        return (state['focus_signature'] or '[NO_FOCUS]')+'#'+hashlib.sha1(
            repr((state.get('focus_bounds'),candidates,readable)).encode()).hexdigest()[:10]
    nodes={}; edges={}; current=key_for(root,state)
    nodes[current]=state
    for step in range(limit):
        route=shortest_pending(current,nodes,edges)
        if route is None:
            record['status']='REACHABLE_FOCUS_GRAPH_SCANNED'; break
        if route:
            key=route[0]
        else:
            key=next(key for key in DIRECTIONS if (current,key) not in edges)
        before=ranges(root)
        range_adjustment=bool(focus and focus.get('range') and key in ('l','r'))
        a.key(key)
        if range_adjustment: time.sleep(2)
        _,after_root,after_focus,after=a.snap(tag+'-'+key)
        if (after['package'],after['window'])!=origin:
            record['status']='DIRECTION_CHANGED_PAGE'; record['unexpected']=after; save()
            raise RuntimeError('Direction changed page: '+str(path))
        if guard is not None:
            try:guard(after_root,after_focus,after)
            except Exception as error:
                record['status']='OBSERVATION_GUARD_FAILED'
                record['guard_error']=repr(error);record['unexpected']=after;save()
                raise
        after_ranges=ranges(after_root)
        changed_keys=[key for key in before.keys() & after_ranges.keys() if before[key]!=after_ranges[key]]
        changed=bool(changed_keys)
        if changed:
            # SeekBars react to arrows. Restore the one-step value immediately;
            # do not send a reverse arrow at a clamped boundary with no change.
            restore={'key':key,'before':before,'after':ranges(after_root),'evidence':after['file']}
            a.key(OPPOSITE[key])
            time.sleep(2)
            _,after_root,after_focus,after=a.snap(tag+'-restore')
            # Font/density changes recreate the Activity. An empty intermediate
            # hierarchy is not a value mismatch; wait for the same ranges to return.
            deadline=time.monotonic()+5
            while not set(changed_keys).issubset(ranges(after_root)) and time.monotonic()<deadline:
                time.sleep(.4)
                _,after_root,after_focus,after=a.snap(tag+'-restore-settle')
            restore['restored']=ranges(after_root); restore['restored_evidence']=after['file']
            record['range_restores'].append(restore)
            if any(restore['restored'].get(key)!=before[key] for key in changed_keys):
                record['status']='RANGE_RESTORE_FAILED'; save()
                raise RuntimeError('Range value did not restore: '+str(path))
        destination=key_for(after_root,after)
        nodes[destination]=after
        edges[(current,key)]=destination
        record['nodes']=nodes
        record['edges'].append({'from':current,'key':key,'to':destination,'evidence':after['file'],
                                'range_changed_and_restored':changed})
        root,focus,state=after_root,after_focus,after
        current=destination
        save()
        print('GRAPH '+str(step)+' '+('/'.join(path))+' '+key+' '+str(after['focus']),flush=True)
    else: record['status']='GRAPH_LIMIT'
    record['end']=a.snap(tag+'-end',True)[3]
    record['unvisited_edges']=[{'node':node,'key':key} for node in nodes for key in DIRECTIONS if (node,key) not in edges]
    if record['unvisited_edges'] and record['status']=='REACHABLE_FOCUS_GRAPH_SCANNED':
        record['status']='REACHED_CONTROLS_WITH_PENDING_EDGES'
    save()
    return record
