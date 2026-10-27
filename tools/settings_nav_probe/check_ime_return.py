"""Verify the actual HAT/A/B return chain across keyboard language settings."""
import argparse
import json
import time
from audit import Audit, OUT, adb
from followup import enter


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true')
    args=p.parse_args();a=Audit();r={'status':'RUNNING','baseline':args.baseline}
    receipt=OUT/('ime-return-baseline.json' if args.baseline else 'ime-return-fixed.json')
    try:
        enter(a,['系统','语言和输入法','虚拟键盘','Android 键盘 (AOSP)'])
        r['keyboard']=a.snap('ime-return-keyboard',True)[3]
        r['stack_before']=adb('dumpsys activity activities')
        a.seek('语言',actionable=True);a.key('a')
        r['languages']=a.snap('ime-return-languages',True)[3]
        r['stack_after_open']=adb('dumpsys activity activities')
        a.key('b');r['observations']=[]
        for _ in range(10):
            s=a.snap('ime-return-observe')[3];r['observations'].append(s)
            if s['window_id']==r['keyboard']['window_id']:break
            time.sleep(.3)
        r['returned_to_actual_keyboard_window']=s['window_id']==r['keyboard']['window_id']
        r['stack_after_back']=adb('dumpsys activity activities')
        if args.baseline:
            r['status']='BASELINE_RETURN_FAILURE_REPRODUCED' if not r['returned_to_actual_keyboard_window'] else 'BASELINE_DID_NOT_REPRODUCE'
        else:
            if not r['returned_to_actual_keyboard_window']:raise RuntimeError('B did not return to keyboard settings')
            a.key('b');r['virtual_keyboard_return']=a.snap('ime-return-virtual-keyboard',True)[3]
            if r['virtual_keyboard_return']['window']!='虚拟键盘':raise RuntimeError('Second B lost virtual keyboard parent')
            r['status']='PASS'
        print(r['status'],flush=True)
    finally:
        a.close();receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
