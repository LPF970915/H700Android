"""Check manual date/time dialogs while preserving clock and automatic settings."""
import json,time
from audit import Audit,OUT,adb,descendants
from followup import enter,top
from graph import graph
from files import focus

def main():
 a=Audit();r={'status':'RUNNING','manual_date_or_time_saved':False};baseline={}
 try:
  for k in ('auto_time','auto_time_zone'):baseline[k]=adb('settings get global '+k).strip()
  r['baseline']=baseline;r['zone_before']=adb('getprop persist.sys.timezone').strip()
  enter(a,['系统','日期和时间'])
  if baseline['auto_time']=='1':
   top(a);a.seek('使用网络提供的时间',actionable=True);a.key('a')
  if adb('settings get global auto_time').strip()!='0':raise RuntimeError('Manual date/time not enabled')
  r['dialogs']=[]
  for title in ('日期','时间'):
   top(a);focus(a,title,expected_package='com.android.settings');_,_,_,before=a.snap('manual-'+title+'-before');a.key('a')
   _,root,_,state=a.snap('manual-'+title+'-dialog',True)
   if state['window_id']==before['window_id']:raise RuntimeError('Manual picker did not open '+title)
   scan=graph(a,['设置','手动日期时间',title],300)
   if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Picker graph incomplete '+title)
   a.key('b');after=a.snap('manual-'+title+'-cancel',True)[3]
   if after['window']!='日期和时间':raise RuntimeError('Picker cancel did not return')
   r['dialogs'].append({'title':title,'entry':state,'graph_status':scan['status'],'cancel':after})
  if baseline['auto_time_zone']=='1':
   top(a);a.seek('使用网络提供的时区',actionable=True);a.key('a')
  if adb('settings get global auto_time_zone').strip()!='0':raise RuntimeError('Manual timezone not enabled')
  top(a);focus(a,'时区',expected_package='com.android.settings');a.key('a');r['timezone_entry']=a.snap('manual-timezone-entry',True)[3]
  scan=graph(a,['设置','手动日期时间','时区'],180);r['timezone_graph']=scan['status']
  if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Timezone graph incomplete')
  a.key('b');r['timezone_return']=a.snap('manual-timezone-cancel',True)[3]
  r['zone_after']=adb('getprop persist.sys.timezone').strip()
  if r['zone_after']!=r['zone_before']:raise RuntimeError('Timezone changed without confirmation')
  r['status']='PASS_MANUAL_DATE_TIME_ZONE_FOCUS_AND_CANCEL';print(r['status'],flush=True)
 except Exception as e:r.update(status='ERROR',error=repr(e));raise
 finally:
  try:
   r['restoration']={}
   for k in ('auto_time','auto_time_zone'):
    if k in baseline and adb('settings get global '+k).strip()!=baseline[k]:
     r['restoration'][k]=a.command('settings put global '+k+' '+baseline[k])
   r['final_flags']={k:adb('settings get global '+k).strip() for k in baseline}
   if r['final_flags']!=baseline:raise RuntimeError('Automatic date/time baseline not restored')
  except Exception as e:r['cleanup_error']=repr(e)
  finally:a.close();(OUT/'datetime-manual-native-20261025.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
