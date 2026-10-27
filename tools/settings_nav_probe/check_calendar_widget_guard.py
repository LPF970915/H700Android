"""Smoke-test optional Calendar widget callbacks; preserve all old crash records."""
import json,time,subprocess
from audit import OUT,adb,ADB,TARGET

def main():
    r={'status':'RUNNING'}
    try:
        r['start']=adb('date "+%m-%d %H:%M:%S.000"').strip()
        r['service']=adb('service check appwidget')
        r['installed']=adb('p=$(pm path com.android.calendar); sha256sum "${p#package:}"')
        if 'ca1f0c9f5c3837674c31acd996b24432d81d1f03e3bddfc3717006df67a7a713' not in r['installed']:raise RuntimeError('Unexpected installed Calendar APK')
        r['broadcast']=adb('am broadcast -a android.appwidget.action.APPWIDGET_UPDATE -n com.android.calendar/.widget.CalendarAppWidgetProvider')
        service=subprocess.run([ADB,'-s',TARGET,'shell','am startservice -n com.android.calendar/.widget.CalendarAppWidgetService'],capture_output=True,text=True,timeout=20)
        r['start_service']={'returncode':service.returncode,'stdout':service.stdout,'stderr':service.stderr}
        time.sleep(8)
        r['new_crashes']=adb('logcat -b crash -d -T "'+r['start']+'"')
        if service.returncode==0:r['stop_service']=adb('am stopservice -n com.android.calendar/.widget.CalendarAppWidgetService')
        if 'FATAL EXCEPTION' in r['new_crashes']:raise RuntimeError('New crash during callback smoke test')
        r['status']='PASS_RECEIVER_SMOKE_NO_NEW_CRASH_SERVICE_START_BLOCKED' if service.returncode else 'PASS_OPTIONAL_WIDGET_CALLBACK_SMOKE_NO_NEW_CRASH'
        r['limit']='Explicit receiver only when background service startup is blocked; asynchronous data-loader callback coverage is not proven.'
        print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:(OUT/'calendar-optional-widget-smoke.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
