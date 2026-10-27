"""Verify Unicode name preservation, two-stage B, and both file view modes."""
import json,shlex,time
from audit import Audit,OUT,adb,descendants
from files import FIXTURE,focus,select_file,open_control
from graph import graph

def main():
    a=Audit();r={'status':'RUNNING'}
    try:
        target=FIXTURE+'/source/中文 空格.txt';before=adb('sha256sum '+shlex.quote(target)).split()[0]
        select_file(a,'中文 空格.txt');open_control(a,'更多选项');r['rename']=open_control(a,'重命名')
        data,root,_,r['initial']=a.snap('files23-unicode-initial',True)
        field=next(n for n in descendants(root) if n.get('visible') and n.get('editable'))
        if field['text']!='中文 空格.txt':raise RuntimeError('Unicode filename changed on rename startup')
        if not any(w.get('type')==2 for w in data['windows']):a.key('a')
        data,root,_,r['keyboard']=a.snap('files23-unicode-keyboard',True)
        if not any(w.get('type')==2 for w in data['windows']):raise RuntimeError('TV keyboard not shown')
        field=next(n for n in descendants(root) if n.get('visible') and n.get('editable'))
        if field['text']!='中文 空格.txt':raise RuntimeError('TV keyboard lost selected Unicode text')
        a.key('b');data,root,_,r['hidden']=a.snap('files23-unicode-hidden',True)
        if any(w.get('type')==2 for w in data['windows']):raise RuntimeError('First B did not hide keyboard')
        a.key('b')
        for _ in range(12):
            _,root,_,state=a.snap('files23-unicode-cancel-observe')
            if state['window_id']!=r['initial']['window_id']:break
            time.sleep(.25)
        else:raise RuntimeError('Second B did not cancel native rename dialog')
        r['canceled']=state
        if state['window']!='source' or adb('sha256sum '+shlex.quote(target)).split()[0]!=before:raise RuntimeError('Cancel changed Unicode fixture or left wrong page')
        r['list']=open_control(a,'列表视图');r['list_graph']=graph(a,['文件','列表布局_v23'],180)['status']
        if r['list_graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('List focus graph incomplete')
        r['grid']=open_control(a,'网格视图');r['after']=a.snap('files23-grid-restored',True)[3];r['status']='PASS_UNICODE_PRESERVED_TWO_STAGE_B_AND_LIST_GRID';print(r['status'],flush=True)
    except Exception as e:r['status']='ERROR';r['error']=repr(e);raise
    finally:a.close();(OUT/'files23-unicode-modes.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
