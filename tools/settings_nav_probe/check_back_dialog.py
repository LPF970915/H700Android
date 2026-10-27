"""Check B hides the real IME first, then cancels without saving device name."""
import json
import time
from audit import Audit, OUT, adb
from followup import enter


def main():
    a=Audit();result={}
    try:
        result['name_before']=adb('settings get global device_name').strip()
        enter(a,['关于手机']);a.seek('设备名称');a.key('a')
        data,_,_,result['entry']=a.snap('back-v13-device-name')
        if not any(w['type']==2 for w in data['windows']):a.key('a');time.sleep(.5)
        data,_,_,result['ime']=a.snap('back-v13-device-name-ime',True)
        if not any(w['type']==2 for w in data['windows']):raise RuntimeError('Actual IME did not open')
        a.key('b');data,_,_,result['hide']=a.snap('back-v13-device-name-hide')
        if any(w['type']==2 for w in data['windows']) or result['hide']['window']!='':
            raise RuntimeError('First B did not only hide IME')
        a.key('b');result['cancel']=a.snap('back-v13-device-name-cancel',True)[3]
        if result['cancel']['window']!='关于手机':raise RuntimeError('Second B did not cancel the dialog')
        result['name_after']=adb('settings get global device_name').strip()
        if result['name_after']!=result['name_before']:raise RuntimeError('Device name changed during cancel test')
        result['status']='B_HIDES_IME_THEN_CANCELS_WITHOUT_CHANGING_DEVICE_NAME'
        print(result['status'],flush=True)
    except Exception as error:
        result['error']=repr(error);raise
    finally:
        a.close();(OUT/'back-dialog-v13.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
