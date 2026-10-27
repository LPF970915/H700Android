"""Open the notification-tone audio file picker and cancel without importing."""
import argparse
import json
import time
from audit import Audit, OUT, adb, descendants
from followup import enter
from files import focus
from graph import graph


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    output=OUT/('ringtone-add-cancel-'+args.tag+'.json')
    if output.exists():raise ValueError('Fresh evidence required')
    a=Audit();r={'status':'RUNNING','audio_imported':False}
    query='settings get system notification_sound; settings get system ringtone; settings get system alarm_alert'
    try:
        r['sounds_before']=adb(query)
        enter(a,['应用和通知','通知'])
        _,root,_,_=a.snap('ringtone-add-notification-dashboard')
        if any(n.get('visible') and n.get('text')=='高级' for n in descendants(root)):
            r['expand_advanced_focus']=focus(a,'高级',expected_package='com.android.settings')
            a.key('a')
            r['expanded_advanced']=a.snap('ringtone-add-expand-advanced',True)[3]
        # The expanded preference is below the initial viewport. Use the real
        # vertical list traversal instead of bounded visible-control BFS.
        a.seek('默认通知提示音',actionable=True)
        r['tone_preference_focus']=a.snap('ringtone-add-actual-preference')[3]
        a.key('a')
        r['tone_picker']=a.snap('ringtone-add-tone-picker',True)[3]
        if r['tone_picker']['package']!='com.android.providers.media':raise RuntimeError('Expected native ringtone picker')
        r['add_focus']=focus(a,'添加通知',expected_package='com.android.providers.media');a.key('a')
        for _ in range(12):
            r['audio_picker']=a.snap('ringtone-add-audio-picker',True)[3]
            if r['audio_picker']['package']=='com.android.documentsui':break
            time.sleep(.2)
        else:raise RuntimeError('Add notification did not open audio file picker')
        r['audio_picker_graph']=graph(a,['通知提示音',args.tag,'添加通知音频选择器不导入'],240)['status']
        if r['audio_picker_graph']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Audio picker graph incomplete')
        a.key('b');r['picker_return']=a.snap('ringtone-add-cancel-file-picker',True)[3]
        if r['picker_return']['package']!='com.android.providers.media':raise RuntimeError('B did not return to tone picker')
        focus(a,'取消',expected_package='com.android.providers.media');a.key('a')
        r['cancelled']=a.snap('ringtone-add-a-cancel-tone-picker',True)[3]
        if r['cancelled']['package']!='com.android.settings' or r['cancelled']['window']!='通知':
            raise RuntimeError('Tone Cancel A did not return to notifications')
        r['sounds_after']=adb(query)
        if r['sounds_after']!=r['sounds_before']:raise RuntimeError('Sound setting changed')
        r['status']='PASS_ADD_NOTIFICATION_AUDIO_PICKER_HAT_GRAPH_B_A_CANCEL_NO_IMPORT'
    except Exception as error:r.update(status='ERROR',error=repr(error));raise
    finally:a.close();output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    print(r['status'],flush=True)


if __name__=='__main__':main()
