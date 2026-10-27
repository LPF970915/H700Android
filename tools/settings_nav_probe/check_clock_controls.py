"""Complete hour/minute/text clock tests without submitting a system time."""
import argparse,json,time
from audit import Audit,OUT,adb,descendants
from followup import enter,top
from files import focus
from graph import graph
PKG='com.android.settings'
def main():
 p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
 if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
 receipt=OUT/('clock-controls-'+args.tag+'.json')
 if receipt.exists():raise ValueError('Fresh tag required')
 a=Audit();r={'status':'RUNNING','system_time_submitted':False};baseline=None
 try:
  baseline=adb('settings get global auto_time').strip();r['auto_time_before']=baseline
  _,root,_,state=a.snap('clock-resume-entry',True)
  if any(n.get('id')=='android:id/hours' for n in descendants(root)):
   a.key('b');state=a.snap('clock-old-dialog-cancelled')[3]
  if state['window']!='日期和时间':enter(a,['系统','日期和时间'])
  if baseline=='1':top(a);a.seek('使用网络提供的时间',actionable=True);a.key('a')
  if adb('settings get global auto_time').strip()!='0':raise RuntimeError('Manual time controls not enabled')
  epoch=int(adb('date +%s').strip());started=time.monotonic()
  top(a);focus(a,'时间',expected_package=PKG);a.key('a');r['entry']=a.snap('clock-fresh-dialog',True)[3]
  focus(a,'hours',expected_package=PKG);a.key('a');r['hour_mode']=a.snap('clock-hour-mode',True)[3]
  focus(a,'7',limit=300,expected_package=PKG);_,_,node,r['hour_target']=a.snap('clock-hour-seven-target',True)
  if not node or 'RadialPickerTouchHelper' not in node.get('class',''):raise RuntimeError('Hour target is not a dial choice')
  a.key('a');_,root,_,r['hour_applied']=a.snap('clock-hour-seven-applied',True)
  if int(next(n.get('text') for n in descendants(root) if n.get('id')=='android:id/hours'))!=7:raise RuntimeError('Hour A failed')
  focus(a,'minutes',expected_package=PKG);a.key('a');focus(a,'25',limit=300,expected_package=PKG)
  a.key('a');_,root,_,r['minute_applied']=a.snap('clock-minute25-applied',True)
  if next(n.get('text') for n in descendants(root) if n.get('id')=='android:id/minutes')!='25':raise RuntimeError('Minute A failed')
  focus(a,'button2',expected_package=PKG)
  _,root,_,r['selection_after_blur']=a.snap('clock-selection-after-blur',True)
  values={n.get('id'):n.get('text') for n in descendants(root) if n.get('id') in ('android:id/hours','android:id/minutes')}
  if int(values['android:id/hours'])!=7 or values['android:id/minutes']!='25':raise RuntimeError('Chosen dial values rolled back on blur')
  r['dials']=[]
  for mode in ('hours','minutes'):
   focus(a,mode,expected_package=PKG);a.key('a');_,root,_,_=a.snap('clock-'+mode+'-graph-entry')
   def dial_values(root):
    return {n.get('desc') for n in descendants(root) if n.get('visible') and 'RadialPickerTouchHelper' in n.get('class','') and n.get('actions',0)&16}
   expected=dial_values(root)
   def mode_guard(root,node,state):
    if dial_values(root)!=expected:raise RuntimeError('Direction changed the clock dial or value')
   scan=graph(a,['时钟',args.tag,mode],260,guard=mode_guard)
   reached={s.get('focus') for s in scan['nodes'].values() if 'RadialPickerTouchHelper' in s.get('focus_signature','')}
   item={'mode':mode,'status':scan['status'],'expected':sorted(expected),'reached':sorted(reached),'missing':sorted(expected-reached)}
   r['dials'].append(item)
   if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED' or item['missing'] or len(expected)<12:raise RuntimeError('Dial graph incomplete')
  _,root,_,r['selection_after_graphs']=a.snap('clock-values-after-graphs',True)
  values={n.get('id'):n.get('text') for n in descendants(root) if n.get('id') in ('android:id/hours','android:id/minutes')}
  if int(values['android:id/hours'])!=7 or values['android:id/minutes']!='25':raise RuntimeError('Dial traversal changed chosen values')
  focus(a,'toggle_mode',expected_package=PKG);a.key('a');data,root,_,r['text_mode']=a.snap('clock-text-mode',True)
  r['editors']=[n.get('id') for n in descendants(root) if n.get('visible') and n.get('editable')]
  if len(r['editors'])<2:raise RuntimeError('Time text editors absent')
  if any(w.get('type')==2 for w in data['windows']):a.key('b')
  scan=graph(a,['时钟',args.tag,'文字模式'],180);r['text_graph']=scan['status']
  if scan['status']!='REACHABLE_FOCUS_GRAPH_SCANNED':raise RuntimeError('Text clock graph incomplete')
  a.key('b');r['cancel']=a.snap('clock-cancel-final',True)[3]
  if r['cancel']['window']!='日期和时间':raise RuntimeError('Cancel failed')
  r['clock_error_s']=round(int(adb('date +%s').strip())-epoch-(time.monotonic()-started),2)
  if abs(r['clock_error_s'])>5:raise RuntimeError('Clock changed beyond elapsed time')
  if baseline=='1':
   top(a);a.seek('使用网络提供的时间',actionable=True);a.key('a')
   if adb('settings get global auto_time').strip()!='1':raise RuntimeError('Controller automatic-time restore failed')
  r['status']='PASS_HOUR_MINUTE_A_BOTH_DIALS_TEXT_MODE_CANCEL_CLOCK_UNCHANGED';print(r['status'],flush=True)
 except Exception as e:r.update(status='ERROR',error=repr(e));raise
 finally:
  try:
   if baseline is not None and adb('settings get global auto_time').strip()!=baseline:r['cleanup_restore']=a.command('settings put global auto_time '+baseline)
  except Exception as e:r['cleanup_error']=repr(e)
  finally:a.close();receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
