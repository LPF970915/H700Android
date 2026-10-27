"""Confirm each Files type chip and verify multi-selection toolbar/menu reachability."""
import json
from audit import Audit,OUT,descendants,label
from files import focus,open_control,select_file
from graph import graph

def main():
    a=Audit();path=OUT/'files25-chips-selection.json';r={'status':'RUNNING'}
    if path.exists():a.close();raise ValueError('Receipt already exists')
    try:
        if a.snap('chips-entry')[3]['window']!='source':raise RuntimeError('Owned source fixture required')
        r['chips']=[]
        for name in ('图片','音频','视频','文档'):
            item={'name':name};focus(a,name);_,_,node,item['before']=a.snap('chip-before',True)
            if node.get('checked'):raise RuntimeError('Expected no active filters')
            a.key('a');_,root,_,item['enabled']=a.snap('chip-enabled',True)
            chip=next(n for n in descendants(root) if n.get('visible') and n.get('class','').endswith('.Chip') and label(n)==name)
            if not chip.get('checked'):raise RuntimeError('A did not enable '+name)
            item['visible_documents']=[label(n) for n in descendants(root) if n.get('visible') and n.get('id','').endswith('/item_root')]
            focus(a,name);a.key('a');_,root,_,item['disabled']=a.snap('chip-disabled',True)
            chip=next(n for n in descendants(root) if n.get('visible') and n.get('class','').endswith('.Chip') and label(n)==name)
            if chip.get('checked'):raise RuntimeError('A did not disable '+name)
            r['chips'].append(item)
        r['selected']=select_file(a,'T.txt.zip');open_control(a,'更多选项');r['select_all']=open_control(a,'全选')
        r['toolbar']=[]
        for target in ('action_mode_close_button','action_menu_delete','sub_menu_list','更多选项'):
            r['toolbar'].append(focus(a,target))
        a.key('a');r['overflow_graph']=graph(a,['文件','多选菜单_补测_v25'],180)['status']
        if r['overflow_graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Selection overflow graph incomplete')
        a.key('b');open_control(a,'action_mode_close_button');r['cancel']=a.snap('selection-canceled-final',True)[3]
        if r['cancel']['window']!='source':raise RuntimeError('Selection did not cancel')
        r['status']='PASS_FOUR_CHIPS_TOGGLE_SELECTION_TOOLBAR_OVERFLOW_AND_CANCEL';print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:a.close();path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
