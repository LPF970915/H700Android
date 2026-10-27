"""Execute a scoped move/extract through controller UI and verify actual file bytes."""
import argparse
import hashlib
import json
import re
import time
import zipfile
from audit import Audit, OUT, adb
from files import FIXTURE, open_control, select_file, focus
from graph import graph


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['move','extract']);args=p.parse_args()
    kind=args.kind;leaf='moved' if kind=='move' else 'T';name='T.txt'
    a=Audit();r={'status':'RUNNING','kind':kind,'leaf':leaf}
    try:
        entry=a.snap('files-transfer-start')[3]
        if entry['window']!='source':raise RuntimeError('Transfer did not start in known source')
        if kind=='move':
            r['expected_hash']=adb('sha256sum '+FIXTURE+'/source/T.txt').split()[0]
            if adb('if [ -e '+FIXTURE+'/moved ]; then echo EXISTS; fi').strip()=='EXISTS':raise RuntimeError('Move fixture already exists')
            a.command('mkdir '+FIXTURE+'/moved')
        else:
            with zipfile.ZipFile(OUT/'files19-owned-compressed.zip') as z:
                r['expected_hash']=hashlib.sha256(z.read('T.txt')).hexdigest()
            r['archive_entry']=open_control(a,'T.txt.zip')
            if r['archive_entry']['after']['window']!='T.txt.zip':raise RuntimeError('Archive browser not entered')
        if adb('if [ -e '+FIXTURE+'/'+leaf+'/T.txt ]; then echo EXISTS; fi').strip()=='EXISTS':raise RuntimeError('Destination must be initially empty')
        r['selection']=select_file(a,name);open_control(a,'更多选项')
        r['picker']=open_control(a,'移动到…' if kind=='move' else '解压到…')
        open_control(a,'显示根目录');focus(a,'RGSP H700');a.key('a')
        open_control(a,'Download');open_control(a,'DPAD_AUDIT_20261024')
        r['destination']=open_control(a,leaf)
        if r['destination']['after']['window']!=leaf:raise RuntimeError('Wrong destination')
        r['graph_status']=graph(a,['文件',kind+'目的地选择器_v19'],150)['status']
        focus(a,'button1');_,_,node,state=a.snap('files-transfer-confirm',True)
        caption=node.get('text','')
        if (kind=='move' and caption!='移动') or (kind=='extract' and not re.search('解压|提取',caption)):
            raise RuntimeError('Unexpected operation confirmation: '+caption)
        r['confirm']=state;a.key('a')
        for _ in range(40):
            done=adb('if [ -f '+FIXTURE+'/'+leaf+'/T.txt ]; then echo PRESENT; fi').strip()=='PRESENT'
            gone=kind!='move' or adb('if [ ! -e '+FIXTURE+'/source/T.txt ]; then echo GONE; fi').strip()=='GONE'
            if done and gone:break
            time.sleep(.3)
        else:raise RuntimeError('Transfer did not complete')
        r['actual_hash']=adb('sha256sum '+FIXTURE+'/'+leaf+'/T.txt').split()[0]
        if r['actual_hash']!=r['expected_hash']:raise RuntimeError('Transfer content mismatch')
        r['after']=a.snap('files-transfer-finished',True)[3];r['status']='PASS'
        print('FILE_'+kind.upper()+'_PASS',flush=True)
    except Exception as error:r['status']='ERROR';r['error']=repr(error);raise
    finally:a.close();(OUT/('files-v19-'+kind+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
