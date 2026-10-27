"""Verify readable editor input, two-stage B, and create one owned directory."""
import json
import re
import time
from audit import Audit, OUT, adb, descendants
from files import FIXTURE, open_control, focus
from graph import graph


def editor(a,tag):
    for _ in range(15):
        data,root,_,state=a.snap(tag,True)
        fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
        if len(fields)==1 and any(w.get('type')==2 for w in data['windows']):
            return fields[0],state
        time.sleep(.2)
    raise RuntimeError('Visible editor and actual TV keyboard not observed')


def main():
    a=Audit();r={'status':'RUNNING','visual_review':'PENDING'}
    try:
        r['rename_open']=open_control(a,'重命名')
        field,state=editor(a,'files19-rename-visible');r['rename_initial']=dict(field=field,state=state)
        if field['text']!='T.txt':raise RuntimeError('Keyboard startup changed the existing file name')
        a.key('r');a.key('a');field,state=editor(a,'files19-rename-typed');r['rename_typed']=dict(field=field,state=state)
        a.key('b');r['rename_hidden']=a.snap('files19-rename-keyboard-hidden',True)[3]
        a.key('b')
        for _ in range(12):
            state=a.snap('files19-rename-cancel-observe')[3]
            if state['window_id']!=r['rename_open']['after']['window_id']:break
            time.sleep(.3)
        else:raise RuntimeError('Second B failed to cancel file rename')
        r['rename_canceled']=state
        if state['window']!='source':raise RuntimeError('Cancel did not return to the source directory')
        if adb('test -f '+FIXTURE+'/source/T.txt && echo ORIGINAL').strip()!='ORIGINAL':raise RuntimeError('Original fixture was not preserved')
        a.key('b');r['new_folder_parent']=a.snap('files19-folder-parent',True)[3]
        if r['new_folder_parent']['window']!='DPAD_AUDIT_20261024':raise RuntimeError('Wrong new-folder parent')
        open_control(a,'更多选项');r['folder_open']=open_control(a,'新建文件夹')
        field,state=editor(a,'files19-new-folder-empty');r['folder_initial']=dict(field=field,state=state)
        a.key('a');field,state=editor(a,'files19-new-folder-typed');r['folder_typed']=dict(field=field,state=state)
        name=field['text']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,24}',name):raise RuntimeError('Unexpected typed directory name')
        if adb('if [ -e '+FIXTURE+'/'+name+' ]; then echo EXISTS; fi').strip()=='EXISTS':raise RuntimeError('Refusing to reuse an existing directory')
        r['new_folder_name']=name;a.key('b')
        r['folder_hidden']=a.snap('files19-new-folder-keyboard-hidden',True)[3]
        r['folder_graph']=graph(a,['文件','新建文件夹对话框_v19'],100)['status']
        focus(a,'button1');r['folder_confirm']=a.snap('files19-new-folder-confirm',True)[3];a.key('a')
        for _ in range(20):
            if adb('if [ -d '+FIXTURE+'/'+name+' ]; then echo CREATED; fi').strip()=='CREATED':break
            time.sleep(.25)
        else:raise RuntimeError('UI directory creation did not create the fixture directory')
        r['after']=a.snap('files19-new-folder-created',True)[3];r['status']='FUNCTIONAL_PASS_PENDING_VISUAL_REVIEW'
        print('FILE_EDITORS_AND_NEW_FOLDER '+name,flush=True)
    except Exception as error:
        r['status']='ERROR';r['error']=repr(error);raise
    finally:
        a.close();(OUT/'files-v19-editors.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
