"""Sample native document scrolling without dumping an entire WebView DOM."""
import json
import subprocess
import time
from audit import Audit, OUT, adb, ADB, TARGET
from followup import enter


def capture(name):
    adb('screencap -p /data/local/tmp/license-audit.png')
    subprocess.run([ADB,'-s',TARGET,'pull','/data/local/tmp/license-audit.png',str(OUT/(name+'.png'))],
                   check=True,capture_output=True)
    return name+'.png'


def main():
    a=Audit();results=[]
    try:
        for index,title in enumerate(('第三方许可','系统 WebView 许可')):
            result={'title':title};results.append(result)
            enter(a,['关于手机','法律信息']);a.seek(title,actionable=True)
            result['before']=a.snap('license-parent-'+str(index))[3]
            a.key('a')
            for _ in range(20):
                activity=adb('dumpsys activity activities | grep mResumedActivity')
                if 'com.android.htmlviewer/' in activity or 'com.android.webview/' in activity:break
                time.sleep(.5)
            else:
                result.update(status='VIEWER_NOT_OBSERVED',activity=activity)
                raise RuntimeError('License viewer did not become foreground: '+title)
            result['activity']=activity;time.sleep(10)
            tag='license-v15-'+str(index)
            result['entry_png']=capture(tag+'-entry')
            a.hold('d');a.hold('d');result['down_png']=capture(tag+'-down')
            a.hold('u');a.hold('u');result['up_png']=capture(tag+'-up')
            a.key('b');result['return_observations']=[]
            for _ in range(10):
                result['return']=a.snap(tag+'-return')[3]
                result['return_observations'].append(result['return'])
                if result['return']['window_id']==result['before']['window_id']:break
                time.sleep(.5)
            else:raise RuntimeError('License viewer did not return to its actual parent')
            result['status']='SCROLL_SAMPLES_CAPTURED_RETURN_VERIFIED_PENDING_VISUAL_REVIEW'
            (OUT/'licenses-v15.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(title,result['status'],flush=True)
    finally:
        a.close();(OUT/'licenses-v15.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
