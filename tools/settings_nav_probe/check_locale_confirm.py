"""Promote English and Chinese with actual A, checking locale and IME retention."""
import argparse,json,time
from audit import Audit,OUT,adb,descendants
from followup import enter,top
from files import focus

TV='com.android.inputmethod.leanback/.service.LeanbackImeService'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    path=OUT/('locale-confirm-'+args.tag+'.json')
    if path.exists():raise ValueError('Fresh tag required')
    a=Audit();r={'status':'RUNNING'}
    try:
        r['before']=adb('settings get system system_locales').strip()
        r['ime_before']=adb('settings get secure default_input_method').strip()
        if r['before'].split(',')[0] not in ('zh-CN','zh-Hans-CN') or 'en-US' not in r['before'] or r['ime_before']!=TV:
            raise RuntimeError('Expected Chinese/English/TV baseline')
        enter(a,['系统','语言和输入法','语言']);r['switches']=[]
        for text,codes in [('English (United States)',('en-US',)),('中文',('zh-CN','zh-Hans-CN'))]:
            top(a)
            if text=='中文':
                _,root,_,_=a.snap('locale-chinese-native-label')
                labels=[n.get('text') for n in descendants(root) if n.get('id')=='com.android.settings:id/label' and '中文' in n.get('text','')]
                if len(labels)!=1:raise RuntimeError('Chinese locale row is ambiguous')
                text=labels[0]
            focus(a,text,expected_package='com.android.settings');item={'focused':a.snap('locale-'+args.tag+'-focused',True)[3]}
            a.key('a');deadline=time.monotonic()+15
            while True:
                value=adb('settings get system system_locales').strip()
                if value.split(',')[0] in codes:break
                if time.monotonic()>deadline:raise RuntimeError('A did not promote '+str(codes))
                time.sleep(.3)
            item.update(locales=value,ime=adb('settings get secure default_input_method').strip(),after=a.snap('locale-'+args.tag+'-applied',True)[3]);r['switches'].append(item)
            if item['ime']!=TV:raise RuntimeError('Locale change replaced the TV IME')
        r['status']='PASS_A_SWITCHES_ENGLISH_AND_CHINESE_TV_IME_RETAINED';print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:
        # No property-based shortcut is used to claim a controller switch passed.
        try:
            r['final_locales']=adb('settings get system system_locales').strip()
            if r.get('before','').split(',')[0] in ('zh-CN','zh-Hans-CN') and not r['final_locales'].startswith('zh-'):
                _,root,_,_=a.snap('locale-restore-check')
                if any(n.get('id')=='com.android.settings:id/dragList' for n in descendants(root)):
                    labels=[n.get('text') for n in descendants(root) if n.get('id')=='com.android.settings:id/label' and '中文' in n.get('text','')]
                    if len(labels)!=1:raise RuntimeError('Chinese recovery row ambiguous')
                    top(a);focus(a,labels[0],expected_package='com.android.settings');a.key('a');time.sleep(1)
                    r['restore_chinese_through_ui']=a.snap('locale-restored-chinese',True)[3]
            if r.get('ime_before')==TV and adb('settings get secure default_input_method').strip()!=TV:
                r['cleanup_restore_ime']=a.command('ime set --user 0 '+TV)
        except Exception as e:r['cleanup_error']=repr(e)
        finally:
            a.close();path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
