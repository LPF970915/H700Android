"""Traverse every owned long-list row in both directions using real HAT input."""
import json,time
from audit import Audit,OUT,adb,descendants,label
from files import focus,open_control

def main():
    a=Audit();r={'status':'RUNNING','forward':[],'reverse':[]}
    try:
        _,root,_,state=a.snap('files25-long-start',True)
        if state['window']=='source':a.key('b')
        open_control(a,'long-list')
        _,root,_,_=a.snap('files25-long-layout')
        if any(n.get('visible') and n.get('desc')=='列表视图' for n in descendants(root)):open_control(a,'列表视图')
        focus(a,'item_000.txt')
        for direction,indices,record in [('d',range(64),'forward'),('u',range(63,-1,-1),'reverse')]:
            for pos,index in enumerate(indices):
                if pos:a.key(direction)
                _,root,node,state=a.snap('files25-long-'+record+'-'+str(index),index in (0,63))
                expected='item_%03d.txt'%index
                if not node or expected not in label(node):raise RuntimeError('Wrong row: expected '+expected+', got '+str(state))
                titles=[n for n in descendants(node) if n.get('text')==expected]
                if not titles:raise RuntimeError('Selected row has no readable filename')
                appbars=[n['bounds'][3] for n in descendants(root) if n.get('visible') and n.get('id','').endswith('/app_bar')]
                title=titles[0]['bounds'];top=max(appbars,default=32);bottom=root['bounds'][3]
                if title[1]<top or title[3]>bottom:raise RuntimeError('Filename obscured: '+str((expected,title,top,bottom)))
                r[record].append({'name':expected,'filename_bounds':title,'appbar_bottom':top,'state':state})
                print(record+' '+expected,flush=True)
        r['status']='PASS_64_ROWS_FORWARD_AND_REVERSE_VISIBLE_FILENAMES'
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:a.close();(OUT/'files25-long-list.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
