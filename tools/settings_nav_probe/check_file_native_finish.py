"""Exercise native RGSP rename and delete only inside the owned audit fixture."""
import json,re,time
from audit import Audit,OUT,adb,descendants
from files import FIXTURE,select_file,open_control,focus

def wait_name(a,tag):
    for _ in range(10):
        data,root,_,state=a.snap(tag,True)
        fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
        if len(fields)==1:return data,fields[0],state
        time.sleep(.2)
    raise RuntimeError('One visible native filename field required')

def main():
    a=Audit();r={'status':'RUNNING'}
    try:
        original=FIXTURE+'/source/T.txt.zip';before=adb('sha256sum '+original).split()[0]
        select_file(a,'T.txt.zip');open_control(a,'更多选项');r['rename']=open_control(a,'重命名')
        data,field,state=wait_name(a,'files-native-rename-initial');r['initial_field']=field;r['initial_state']=state
        if field['text']!='T.txt.zip':raise RuntimeError('Rename keyboard lost original filename')
        if not any(w.get('type')==2 for w in data['windows']):a.key('a')
        a.key('r');a.key('a');_,field,state=wait_name(a,'files-native-rename-typed');new=field['text'];r['typed_field']=field;r['typed_state']=state
        if new=='T.txt.zip' or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',new):raise RuntimeError('Unexpected filename after real keyboard input')
        target=FIXTURE+'/source/'+new
        if adb('if [ -e '+target+' ]; then echo EXISTS; fi').strip()=='EXISTS':raise RuntimeError('Refusing existing rename target')
        a.key('b');r['hidden']=a.snap('files-native-rename-hidden',True)[3]
        focus(a,'button1');a.key('a')
        for _ in range(20):
            if adb('if [ -f '+target+' ]; then echo EXISTS; fi').strip()=='EXISTS':break
            time.sleep(.25)
        else:raise RuntimeError('UI rename did not complete')
        r['renamed']=a.snap('files-native-renamed',True)[3];r['renamed_path']=target;r['sha256']=adb('sha256sum '+target).split()[0]
        if r['sha256']!=before:raise RuntimeError('Renamed content changed')
        # Cleanup is explicitly separate from controller-only pass evidence.
        a.command('mv '+target+' '+original);r['rename_cleanup']='UART restored owned fixture name after verified UI rename'
        a.key('b');open_control(a,'moved');select_file(a,'T.txt');r['delete_dialog']=open_control(a,'删除')
        r['delete_cancel_focus']=focus(a,'button2');a.key('a');r['delete_cancel']=a.snap('files-native-delete-canceled',True)[3]
        victim=FIXTURE+'/moved/T.txt'
        if adb('if [ -f '+victim+' ]; then echo EXISTS; fi').strip()!='EXISTS':raise RuntimeError('Cancel deleted fixture')
        select_file(a,'T.txt');open_control(a,'删除');r['delete_positive']=focus(a,'button1');a.key('a')
        for _ in range(20):
            if adb('if [ ! -e '+victim+' ]; then echo ABSENT; fi').strip()=='ABSENT':break
            time.sleep(.25)
        else:raise RuntimeError('UI delete did not complete')
        r['delete_done']=a.snap('files-native-delete-done',True)[3];r['deleted_owned_path']=victim;r['status']='FUNCTIONAL_PASS_PENDING_VISUAL_REVIEW'
        print('FILE_NATIVE_RENAME_DELETE_PASS',flush=True)
    except Exception as e:r['status']='ERROR';r['error']=repr(e);raise
    finally:a.close();(OUT/'files-native-rename-delete.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
