"""Exercise non-destructive Files menu actions through the controller."""
import argparse,json,time
from audit import Audit,OUT,adb,descendants,label
from files import FIXTURE,focus,open_control,select_file,enter_source
from graph import graph

def main():
    p=argparse.ArgumentParser();p.add_argument('part',choices=['sort','roots','selection','folder-cancel','info','search','storage-toggle','new-window','grid-clip']);args=p.parse_args()
    a=Audit();r={'status':'RUNNING','part':args.part}
    try:
        if args.part=='sort':
            open_control(a,'更多选项');open_control(a,'排序依据…')
            _,root,_,_=a.snap('files25-sort-options')
            # Sorting dialog has eight stable native options, virtualized to fit.
            r['choices']=[]
            for index in range(8):
                # Each reopen starts on the currently selected row.
                for _ in range(2):a.hold('u')
                for _ in range(index):a.key('d')
                _,root,node,state=a.snap('files25-sort-choice-'+str(index),True)
                if not node or not node.get('class','').endswith('CheckedTextView'):raise RuntimeError('Sort option not focused')
                chosen=label(node);a.key('a')
                r['choices'].append({'index':index,'label':chosen,'state':state,'returned':a.snap('files25-sort-applied')[3]})
                open_control(a,'更多选项');open_control(a,'排序依据…')
                _,root,_,state=a.snap('files25-sort-check-'+str(index))
                checked=[n.get('text') for n in descendants(root) if n.get('checked')]
                # A checked row outside the current viewport can be omitted. Focus it again before verifying.
                for _ in range(2):a.hold('u')
                for _ in range(index):a.key('d')
                _,root,node,state=a.snap('files25-sort-checked-visible-'+str(index))
                if label(node)!=chosen or not node.get('checked'):raise RuntimeError('Sort selection not retained: '+chosen)
            for _ in range(2):a.hold('u')
            a.key('a');r['restored']='File name ascending through actual UI'
        elif args.part=='roots':
            open_control(a,'显示根目录');r['roms']=open_control(a,'ROMS');_,root,_,state=a.snap('files25-roms-root',True)
            if state['window']!='ROMS':raise RuntimeError('ROMS root not entered')
            r['root_state']=state;r['graph']=graph(a,['文件','ROMS根_v25'],220)['status']
            if r['graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('ROMS root focus graph incomplete')
            r['return']=enter_source(a,'RGSP H700')
        elif args.part=='selection':
            select_file(a,'T.txt.zip');open_control(a,'更多选项');r['all']=open_control(a,'全选')
            _,root,_,state=a.snap('files25-all-selected',True)
            expected=int(adb('find '+FIXTURE+'/source -mindepth 1 -maxdepth 1 | wc -l').strip())
            if '已选择 '+str(expected)+' 项'!=state['window']:raise RuntimeError('Selection count mismatch: '+str(state))
            r['selected_count']=expected;r['graph']=graph(a,['文件','多选工具栏_v25'],180)['status']
            if r['graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Multi-selection graph incomplete')
            open_control(a,'更多选项');r['overflow_graph']=graph(a,['文件','多选菜单_v25'],160)['status']
            if r['overflow_graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Multi-selection menu incomplete')
            a.key('b');open_control(a,'action_mode_close_button');r['canceled']=a.snap('files25-selection-canceled',True)[3]
        elif args.part=='folder-cancel':
            before=adb('ls -1A '+FIXTURE+'/source');open_control(a,'更多选项');r['open']=open_control(a,'新建文件夹')
            data,root,_,_=a.snap('files25-folder-empty',True)
            if any(w.get('type')==2 for w in data['windows']):a.key('b')
            focus(a,'button2');a.key('a');r['canceled']=a.snap('files25-folder-canceled',True)[3]
            if r['canceled']['window']!='source' or before!=adb('ls -1A '+FIXTURE+'/source'):raise RuntimeError('New-folder cancel changed directory')
        elif args.part=='info':
            select_file(a,'T.txt.zip');open_control(a,'更多选项');r['open']=open_control(a,'获取信息')
            r['graph']=graph(a,['文件','完整详情滚动_v25'],220)['status']
            if r['graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Info scroll graph incomplete')
            a.key('b');r['returned']=a.snap('files25-info-back',True)[3]
        elif args.part=='search':
            r['open']=open_control(a,'搜索')
            data,root,_,state=a.snap('files25-search-editor',True)
            field=next(n for n in descendants(root) if n.get('visible') and n.get('editable'))
            r['initial_field']=field
            if not any(w.get('type')==2 for w in data['windows']):focus(a,'search_src_text');a.key('a')
            a.key('r');a.key('a');data,root,_,r['typed']=a.snap('files25-search-typed',True)
            field=next(n for n in descendants(root) if n.get('visible') and n.get('editable'))
            if not field.get('text'):raise RuntimeError('Actual TV keyboard did not enter search text')
            r['query']=field['text'];a.key('b')
            r['clear_focus']=focus(a,'search_close_btn');a.key('a')
            _,root,_,r['cleared']=a.snap('files25-search-cleared',True)
            fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
            # Android's AX EditText exposes its localized hint as text when empty.
            if fields and fields[0].get('text') not in ('','搜索…','搜索...'):raise RuntimeError('Clear query left search text')
            data,root,_,_=a.snap('files25-search-hide-if-needed')
            if any(w.get('type')==2 for w in data['windows']):a.key('b')
            if fields:open_control(a,'收起')
            r['returned']=a.snap('files25-search-back',True)[3]
        elif args.part=='storage-toggle':
            def scan_drawer(tag):
                # The internal root is below the initially visible media roots.
                # Check all actually visited drawer viewports, not only its top.
                found=set();states=[];previous=None;repeated=0
                for _ in range(35):
                    _,root,_,state=a.snap(tag);states.append(state)
                    found.update(n.get('text') for n in descendants(root) if n.get('visible') and n.get('text'))
                    key=state['focus_signature']
                    repeated=repeated+1 if key==previous else 0;previous=key
                    if repeated>=3:break
                    a.key('d')
                else:raise RuntimeError('Drawer did not reach a lower boundary')
                return {'visible_text_across_viewports':sorted(found),'walk':states}
            open_control(a,'更多选项');r['hidden']=open_control(a,'隐藏内部存储空间')
            open_control(a,'显示根目录');r['drawer_hidden']=scan_drawer('files25-internal-hidden')
            if 'RGSP H700' in r['drawer_hidden']['visible_text_across_viewports']:raise RuntimeError('Internal root remained shown')
            a.key('b');open_control(a,'更多选项');r['shown']=open_control(a,'显示内部存储空间')
            open_control(a,'显示根目录');r['drawer_shown']=scan_drawer('files25-internal-shown')
            if 'RGSP H700' not in r['drawer_shown']['visible_text_across_viewports']:raise RuntimeError('Internal root did not return')
            a.key('b')
        elif args.part=='new-window':
            r['before']=a.snap('files25-window-before',True)[3]
            open_control(a,'更多选项');r['opened']=open_control(a,'新建窗口')
            for _ in range(10):
                _,root,_,state=a.snap('files25-window-observe',True)
                if state['window_id']!=r['before']['window_id']:break
                time.sleep(.3)
            else:raise RuntimeError('New window did not create another activity window')
            r['new']=state;r['activities']=adb('dumpsys activity activities | grep -E "TaskRecord|com.android.documentsui/.files.FilesActivity|mResumedActivity"')
            r['back_path']=[]
            for _ in range(8):
                a.key('b');state=a.snap('files25-window-back',True)[3];r['back_path'].append(state)
                if state['window_id']==r['before']['window_id']:break
                if state['package']!='com.android.documentsui':raise RuntimeError('Back left Files before original window returned')
            else:raise RuntimeError('B path did not return to original Files window')
            r['returned']=state
        elif args.part=='grid-clip':
            _,root,_,_=a.snap('files25-grid-layout')
            if any(n.get('visible') and n.get('desc')=='网格视图' for n in descendants(root)):open_control(a,'网格视图')
            focus(a,'000_refresh_check.txt');_,root,_,r['selected']=a.snap('files25-grid-clip',True)
            r['service']=adb('dumpsys activity service com.roc.rgsp.navtrial/.NavigationService')
            import re
            b=re.search(r'visibleBounds=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]',r['service'])
            appbar=max(n['bounds'][3] for n in descendants(root) if n.get('visible') and n.get('id','').endswith('/app_bar'))
            if not b or int(b[2])<appbar:raise RuntimeError('Ring still covers Files appbar')
        r['status']='PASS_CONTROLLER_'+args.part.upper();print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:a.close();(OUT/('files25-tail-'+args.part+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
