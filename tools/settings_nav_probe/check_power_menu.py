"""Check the native global-actions focus and cancel path; never confirm power off."""
import argparse,json,time
from audit import Audit,OUT,descendants,label,adb
from power_input import open_power_menu

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);p.add_argument('--baseline',action='store_true');args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    path=OUT/('power-menu-'+args.tag+'.json')
    if path.exists():raise ValueError('Fresh tag required')
    a=Audit();r={'status':'RUNNING','power_off_confirmed':False,'restart_confirmed':False,'opening':'Actual axp2202-pek power evdev hold; traversal uses actual controller input node'}
    try:
        r['before']=a.snap('power-'+args.tag+'-before',True)[3]
        r['open']=open_power_menu(a)
        for _ in range(10):
            _,root,node,state=a.snap('power-'+args.tag+'-entry',True)
            if state['package']=='com.android.systemui' and any('global_actions' in n.get('id','') for n in descendants(root)):break
            time.sleep(.3)
        else:raise RuntimeError('Native global actions window not shown')
        r['entry']=state;r['actions']=[{'id':n.get('id'),'label':label(n),'focusable':n.get('focusable'),'bounds':n.get('bounds')} for n in descendants(root) if n.get('visible') and n.get('clickable')]
        r['walk']=[]
        for key in ['d']*8+['u']*8+['r']*8+['l']*8:
            a.key(key);_,root,node,state=a.snap('power-'+args.tag+'-'+key,True);r['walk'].append(state)
            if state['package']!='com.android.systemui':raise RuntimeError('Direction left power menu')
        seen={s.get('focus') for s in r['walk'] if s.get('focus')}
        r['focused_labels']=sorted(seen)
        r['unreached_actions']=[x['label'] for x in r['actions'] if x['id'] not in (
            'android:id/content','com.android.systemui:id/global_actions_view') and x['label'] not in seen]
        a.key('b');_,cancel_root,_,r['cancel']=a.snap('power-'+args.tag+'-cancel',True)
        # The lock screen also belongs to SystemUI; check the dialog itself.
        if any('global_actions' in n.get('id','') for n in descendants(cancel_root)):
            raise RuntimeError('B did not cancel global actions')
        if not args.baseline and not ('关机' in seen and any(x in seen for x in ('重新启动','重启'))):
            raise RuntimeError('Shutdown and Restart were not both focused')
        if not args.baseline and r['unreached_actions']:raise RuntimeError('Power menu actions not reached: '+str(r['unreached_actions']))
        r['surfaceflinger_pid']=adb('pidof surfaceflinger').strip()
        if not r['surfaceflinger_pid'].isdecimal():raise RuntimeError('Ambiguous compositor PID')
        logs=adb('logcat -d -b all --pid='+r['surfaceflinger_pid'])
        r['gpu_errors']=[line for line in logs.splitlines() if any(marker in line for marker in (
            'Aborting GPU composition','Failed to bind framebuffer','Crop rectangle dimensions not equal'))]
        if not args.baseline and r['gpu_errors']:raise RuntimeError('Graphics error during actual power-menu test')
        r['status']='BASELINE_RECORDED' if args.baseline else 'PASS_NATIVE_POWER_ACTION_FOCUS_AND_B_CANCEL'
        print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:a.close();path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
