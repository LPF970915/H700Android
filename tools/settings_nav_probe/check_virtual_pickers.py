"""Validate action-only calendar/clock cells through HAT/A, cancelling all changes."""
import argparse,calendar,datetime,json,time
from audit import Audit,OUT,adb,descendants,label
from followup import enter,top
from files import focus
from graph import graph

PKG='com.android.settings'
def main():
 p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
 if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
 receipt=OUT/('virtual-pickers-'+args.tag+'.json')
 if receipt.exists():raise ValueError('New tag required')
 a=Audit();r={'status':'RUNNING','date_time_saved':False};baseline=None
 try:
  baseline=adb('settings get global auto_time').strip();r['auto_time_before']=baseline
  r['date_before']=adb('date +%F').strip();today=datetime.date.fromisoformat(r['date_before'])
  enter(a,['系统','日期和时间'])
  if baseline=='1':top(a);a.seek('使用网络提供的时间',actionable=True);a.key('a')
  if adb('settings get global auto_time').strip()!='0':raise RuntimeError('Manual controls not enabled')
  clock_before=int(adb('date +%s').strip());clock_started=time.monotonic()
  top(a);focus(a,'日期',expected_package=PKG);a.key('a');_,root,_,r['date_entry']=a.snap('virtual-date-entry',True)
  if r['date_entry']['navigation_version']!=28:raise RuntimeError('Expected Nav v28')
  pager=next(n['bounds'] for n in descendants(root) if n.get('id')=='android:id/day_picker_view_pager')
  target=today.day%28+1
  candidates=[n for n in descendants(root) if n.get('text')==str(target) and not n.get('clickable') and n.get('actions',0)&16 and n['bounds'][0]>=pager[0] and n['bounds'][2]<=pager[2]]
  if len(candidates)!=1:raise RuntimeError('Current-month virtual date ambiguous')
  focus(a,candidates[0]['desc'],expected_package=PKG);_,_,node,r['day_focus']=a.snap('virtual-date-target',True)
  if not node or node.get('clickable') or not node.get('actions',0)&16:raise RuntimeError('Not an action-only date cell')
  a.key('a');_,root,_,r['day_applied']=a.snap('virtual-date-applied',True)
  header=next(n.get('text','') for n in descendants(root) if n.get('id')=='android:id/date_picker_header_date')
  if str(target) not in header:raise RuntimeError('A did not select virtual date')
  month_suffix=candidates[0]['desc'][len(str(target)):]
  def month_guard(root,node,state):
   for n in descendants(root):
    if n.get('visible') and n.get('actions',0)&16 and not n.get('clickable') and n.get('text','').isdigit():
     b=n.get('bounds',[0,0,0,0])
     if b[0]>=pager[0] and b[2]<=pager[2] and not n.get('desc','').endswith(month_suffix):
      raise RuntimeError('Direction changed the displayed calendar month')
  scan=graph(a,['虚拟控件',args.tag,'日期'],420,guard=month_guard);r['date_graph']=scan['status']
  expected={str(x) for x in range(1,calendar.monthrange(today.year,today.month)[1]+1)}
  reached={s.get('focus') for s in scan['nodes'].values()}
  r['unreached_days']=sorted(expected-reached)
  r['offscreen_day_focus']=[s for s in scan['nodes'].values() if s.get('focus') in expected and not (s['focus_bounds'][0]>=pager[0] and s['focus_bounds'][2]<=pager[2])]
  if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED' or r['unreached_days'] or r['offscreen_day_focus']:raise RuntimeError('Calendar grid coverage/viewport failed')
  focus(a,'date_picker_header_year',expected_package=PKG);a.key('a');r['year_picker']=a.snap('virtual-year-picker',True)[3]
  focus(a,str(today.year+1),expected_package=PKG);a.key('a');_,root,_,r['year_applied']=a.snap('virtual-year-applied',True)
  year=next(n.get('text','') for n in descendants(root) if n.get('id')=='android:id/date_picker_header_year')
  if str(today.year+1) not in year:raise RuntimeError('Year picker A failed')
  a.key('b');r['date_cancel']=a.snap('virtual-date-cancel',True)[3]
  if r['date_cancel']['window']!='日期和时间':raise RuntimeError('Date cancel failed')
  top(a);focus(a,'时间',expected_package=PKG);a.key('a');_,root,_,r['time_entry']=a.snap('virtual-time-entry',True)
  expected_hours={n.get('desc') for n in descendants(root) if n.get('visible') and 'RadialPickerTouchHelper' in n.get('class','') and n.get('actions',0)&16}
  if len(expected_hours)<12:raise RuntimeError('Clock does not expose its hour choices')
  scan=graph(a,['虚拟控件',args.tag,'小时'],240);r['hour_graph']=scan['status']
  reached={s.get('focus') for s in scan['nodes'].values() if 'RadialPickerTouchHelper' in s.get('focus_signature','')}
  r['unreached_hours']=sorted(expected_hours-reached)
  if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED' or r['unreached_hours']:raise RuntimeError('Clock hour coverage failed')
  focus(a,'7',expected_package=PKG);a.key('a');_,root,_,r['hour_applied']=a.snap('virtual-hour-applied',True)
  hour=next(n.get('text','') for n in descendants(root) if n.get('id')=='android:id/hours')
  if int(hour)!=7:raise RuntimeError('A did not select virtual hour')
  focus(a,'25',expected_package=PKG);a.key('a');_,root,_,r['minute_applied']=a.snap('virtual-minute-applied',True)
  minute=next(n.get('text','') for n in descendants(root) if n.get('id')=='android:id/minutes')
  if minute!='25':raise RuntimeError('A did not select virtual minute')
  expected_minutes={n.get('desc') for n in descendants(root) if n.get('visible') and 'RadialPickerTouchHelper' in n.get('class','') and n.get('actions',0)&16}
  scan=graph(a,['虚拟控件',args.tag,'分钟'],240);r['minute_graph']=scan['status']
  reached={s.get('focus') for s in scan['nodes'].values() if 'RadialPickerTouchHelper' in s.get('focus_signature','')}
  r['unreached_minutes']=sorted(expected_minutes-reached)
  if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED' or r['unreached_minutes']:raise RuntimeError('Clock minute graph incomplete')
  focus(a,'toggle_mode',expected_package=PKG);a.key('a');data,root,_,r['text_mode']=a.snap('virtual-clock-text-mode',True)
  r['time_editors']=[n.get('id') for n in descendants(root) if n.get('visible') and n.get('editable')]
  if len(r['time_editors'])<2:raise RuntimeError('Time text mode editors absent')
  if any(w.get('type')==2 for w in data['windows']):a.key('b')
  scan=graph(a,['虚拟控件',args.tag,'文字时间'],160);r['text_graph']=scan['status']
  if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Time text controls incomplete')
  a.key('b');r['time_cancel']=a.snap('virtual-time-cancel',True)[3]
  if r['time_cancel']['window']!='日期和时间':raise RuntimeError('Time cancel failed')
  r['date_after']=adb('date +%F').strip()
  if r['date_after']!=r['date_before']:raise RuntimeError('System date changed despite cancel')
  r['clock_delta_error_s']=round(int(adb('date +%s').strip())-clock_before-(time.monotonic()-clock_started),2)
  if abs(r['clock_delta_error_s'])>5:raise RuntimeError('Clock changed beyond ordinary elapsed time')
  if baseline=='1':
   top(a);a.seek('使用网络提供的时间',actionable=True);a.key('a')
   r['auto_time_restored_by_controller']=adb('settings get global auto_time').strip()=='1'
   if not r['auto_time_restored_by_controller']:raise RuntimeError('Controller did not restore automatic time')
  r['status']='PASS_ALL_CURRENT_MONTH_DAYS_YEAR_HOUR_MINUTE_TEXT_AND_CANCEL';print(r['status'],flush=True)
 except Exception as e:r.update(status='ERROR',error=repr(e));raise
 finally:
  try:
   if baseline is not None and adb('settings get global auto_time').strip()!=baseline:r['restore_auto_time']=a.command('settings put global auto_time '+baseline)
  except Exception as e:r['cleanup_error']=repr(e)
  finally:a.close();receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
