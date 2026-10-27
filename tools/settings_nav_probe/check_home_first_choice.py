"""Reproduce first HOME selection, then restore the exact original HOME holder."""
import argparse,json,time,re
from audit import Audit,OUT,adb,descendants,label

HOME='com.overdevs.at4k/.MainActivity'
PKG='com.overdevs.at4k'

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--native-framework',action='store_true');g=p.add_mutually_exclusive_group();g.add_argument('--confirm-once',action='store_true');g.add_argument('--confirm-always',action='store_true');args=p.parse_args()
    if not args.tag.replace('-','').replace('_','').isalnum():raise ValueError('Invalid tag')
    target=OUT/('home-first-choice-'+args.tag+'.json')
    if target.exists():raise ValueError('Fresh evidence tag required')
    a=Audit();r={'status':'RUNNING','physical_factory_boot':False};changed=False
    try:
        if args.native_framework:
            r['framework_sha256']=adb('sha256sum /system/framework/framework-res.apk').split()[0]
            if r['framework_sha256']!='a8e4d04bdc7a37120c143a781204d9166cd76c96f108f52cc2d789884f5d3d86':raise RuntimeError('Unexpected native framework resource APK')
            r['runtime_overlays']=adb('cmd overlay list --user 0')
            if '[x] com.roc.rgsp.dpad.frameworkoverlay' in r['runtime_overlays']:raise RuntimeError('Legacy trial overrides native HOME layouts')
            a.key('wake')
            keyguard=adb('dumpsys activity service com.android.systemui/.SystemUIService')
            if re.search(r'^\s*mState=1 \(KGRD\)',keyguard,re.M):a.key('a')
        r['home_before']=adb('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME')
        if HOME not in r['home_before']:raise RuntimeError('Expected AT4K baseline; refusing to alter another default')
        a.key('b')
        changed=True;r['remove_role']=a.command('cmd role remove-role-holder --user 0 android.app.role.HOME '+PKG)
        r['clear_preference']=a.command('CLASSPATH=/data/local/tmp/home-preference-fixture.jar app_process /system/bin HomePreferenceFixture --clear-at4k-home')
        r['home_without_role']=adb('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME')
        r['launch']=a.command('am start -a android.intent.action.MAIN -c android.intent.category.HOME -n android/com.android.internal.app.ResolverActivity')
        for _ in range(10):
            _,root,node,state=a.snap('home-first-'+args.tag+'-entry',True)
            if state['package']=='android' and any(n.get('id')=='android:id/resolver_list' for n in descendants(root)):break
            time.sleep(.3)
        else:raise RuntimeError('HOME resolver not shown')
        r['entry']=state
        if any(n.get('text')=='使用其他应用' and n.get('visible') for n in descendants(root)):raise RuntimeError('Still using previously-chosen layout')
        # Native ListView owns the row selection, so use actual key movement/A.
        for _ in range(6):a.key('u')
        _,root,node,r['first_row']=a.snap('home-first-'+args.tag+'-first-row',True)
        if 'AT4K Launcher' not in label(node):raise RuntimeError('AT4K first row not focused')
        a.key('a');_,root,node,r['selected']=a.snap('home-first-'+args.tag+'-selected',True)
        buttons=[n for n in descendants(root) if n.get('id') in ('android:id/button_once','android:id/button_always')]
        r['buttons_after_selection']=[{k:n.get(k) for k in ('id','text','enabled','visible','bounds')} for n in buttons]
        if not buttons or not any(n.get('enabled') for n in buttons):raise RuntimeError('A did not enable confirmation buttons')
        r['walk']=[]
        for key in ['d']*5+['r','l','u','r','d','r','l']:
            a.key(key);_,root,node,state=a.snap('home-first-'+args.tag+'-'+key,True);r['walk'].append(state)
            confirm_id='android:id/button_always' if args.confirm_always else 'android:id/button_once'
            if (args.confirm_once or args.confirm_always) and node and node.get('id')==confirm_id and node.get('enabled'):
                a.key('a');r['launch_observations']=[]
                for _ in range(10):
                    r['launch_result']=a.snap('home-first-'+args.tag+'-launched',True)[3];r['launch_observations'].append(r['launch_result'])
                    if r['launch_result']['package']==PKG:break
                    time.sleep(.3)
                else:raise RuntimeError('Confirmation did not launch selected AT4K')
                r['home_after_confirmation']=adb('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME')
                if args.confirm_always and HOME not in r['home_after_confirmation']:raise RuntimeError('Always did not save selected HOME')
                r['status']='PASS_FIRST_HOME_ALWAYS_CONFIRMED' if args.confirm_always else 'PASS_FIRST_HOME_ONCE_CONFIRMED';break
        else:
            if args.confirm_once or args.confirm_always:raise RuntimeError('Enabled confirmation footer not reachable')
            r['status']='BASELINE_RECORDED'
        print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:
        if changed:
            r['restore']=a.command('cmd package set-home-activity --user 0 '+HOME)
            r['home_after']=adb('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME')
            if HOME not in r['home_after']:r['restore_failed']=True
        a.close();target.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
