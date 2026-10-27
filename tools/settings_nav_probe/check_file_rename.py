"""Rename one owned fixture using the real TV keyboard and controller only."""
import hashlib
import argparse
import json
import re
import time
from audit import Audit, OUT, adb, descendants
from files import FIXTURE, open_control, focus
from graph import graph


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='v18');args=parser.parse_args()
    a=Audit();r={'status':'RUNNING','fixture':FIXTURE}
    try:
        r['hash_before']=adb('sha256sum '+FIXTURE+'/source/sample.txt').split()[0]
        r['open']=open_control(a,'重命名')
        for _ in range(12):
            data,root,_,state=a.snap('files-rename-editor',True)
            if any(w.get('type')==2 for w in data['windows']):break
            time.sleep(.2)
        else:raise RuntimeError('Rename dialog did not open the TV keyboard')
        fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
        if len(fields)!=1 or fields[0].get('text')!='sample.txt':raise RuntimeError('Unexpected rename target')
        r['before_typing']=state
        # One real A chooses the TV keyboard's currently focused character.
        a.key('a');data,root,_,state=a.snap('files-rename-typed',True)
        fields=[n for n in descendants(root) if n.get('visible') and n.get('editable')]
        name=fields[0].get('text','') if len(fields)==1 else ''
        if name=='sample.txt' or not re.fullmatch(r'[A-Za-z0-9_-]{1,24}\.txt',name):
            raise RuntimeError('Controller did not produce a safe fixture filename: '+repr(name))
        r['new_name']=name;r['after_typing']=state
        a.key('b');r['hidden']=a.snap('files-rename-hide-keyboard',True)[3]
        r['graph_status']=graph(a,['文件','重命名对话框_'+args.tag],100)['status']
        focus(a,'button1');_,root,node,state=a.snap('files-rename-confirm-focus',True)
        if not node or not node.get('enabled') or not node.get('id','').endswith('/button1'):
            raise RuntimeError('Rename confirmation not focused')
        r['confirm']=state;a.key('a')
        for _ in range(20):
            if adb('if [ -f '+FIXTURE+'/source/'+name+' ] && [ ! -e '+FIXTURE+'/source/sample.txt ]; then echo RENAMED; fi').strip()=='RENAMED':break
            time.sleep(.25)
        else:raise RuntimeError('UI rename did not change the owned fixture')
        r['hash_after']=adb('sha256sum '+FIXTURE+'/source/'+name).split()[0]
        if r['hash_after']!=r['hash_before']:raise RuntimeError('Rename changed fixture content')
        r['after']=a.snap('files-rename-complete',True)[3];r['status']='PASS'
        print('FILE_RENAME_PASS '+name,flush=True)
    except Exception as error:
        r['status']='ERROR';r['error']=repr(error);raise
    finally:
        a.close();(OUT/('files-'+args.tag+'-rename.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
