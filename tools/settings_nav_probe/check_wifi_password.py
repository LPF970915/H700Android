"""Verify a real saved-network-independent WPA2 password editor; cancel without connecting."""
import argparse,json,time
from audit import Audit,OUT,adb,descendants
from followup import enter,top
from files import focus

PKG='com.android.settings'
TV='com.android.inputmethod.leanback/.service.LeanbackImeService'
def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    receipt=OUT/('wifi-password-'+args.tag+'.json')
    if receipt.exists():raise ValueError('New tag required')
    a=Audit();r={'status':'RUNNING','network_saved':False,'connect_pressed':False}
    try:
        if adb('settings get secure default_input_method').strip()!=TV:raise RuntimeError('TV IME is not default')
        r['baseline']=adb('dumpsys wifi | grep -E "Wi-Fi is|mWifiInfo"')
        enter(a,['网络和互联网','WLAN']);top(a);a.seek('添加网络',actionable=True);a.key('a')
        data,root,_,r['entry']=a.snap('wifi-password-entry',True)
        if any(w.get('type')==2 for w in data['windows']):a.key('b')
        focus(a,'security',expected_package=PKG);a.key('a')
        _,root,_,r['security_picker']=a.snap('wifi-security-picker',True)
        candidates=[n.get('text') for n in descendants(root) if n.get('visible') and 'WPA' in n.get('text','') and 'EAP' not in n.get('text','') and '企业' not in n.get('text','')]
        if not candidates:raise RuntimeError('No personal WPA security option')
        focus(a,candidates[0],expected_package=PKG);a.key('a')
        focus(a,'password',expected_package=PKG);r['password_focus']=a.snap('wifi-password-field-focused',True)[3]
        a.key('a');data,root,_,r['keyboard']=a.snap('wifi-password-tv-keyboard',True)
        if not any(w.get('type')==2 and w.get('root',{}).get('package')=='com.android.inputmethod.leanback' for w in data['windows']):
            raise RuntimeError('Actual TV keyboard window absent')
        field=next(n for n in descendants(root) if n.get('id')=='com.android.settings:id/password')
        r['before_text_redacted']=field.get('text')=='[REDACTED]'
        a.key('d');a.key('a');data,root,_,r['typed']=a.snap('wifi-password-dpad-down-a',True)
        field=next(n for n in descendants(root) if n.get('id')=='com.android.settings:id/password')
        r['typed_text_redacted']=field.get('text')=='[REDACTED]'
        a.key('b');data,root,_,r['keyboard_hidden']=a.snap('wifi-password-hide',True)
        if any(w.get('type')==2 for w in data['windows']):raise RuntimeError('B failed to hide keyboard')
        # Only this empty Add Network fixture is exposed, never a saved password.
        focus(a,'show_password',expected_package=PKG);a.key('a')
        _,root,_,r['owned_character_visible']=a.snap('wifi-password-owned-character-visible',True)
        field=next(n for n in descendants(root) if n.get('id')=='com.android.settings:id/password')
        r['owned_test_character']=field.get('text','')
        if not r['owned_test_character'] or r['owned_test_character']=='[REDACTED]':
            raise RuntimeError('Owned test character not observable after Show password')
        a.seek('取消',actionable=True)
        _,_,cancel,r['cancel_focus']=a.snap('wifi-password-cancel-focus',True)
        if cancel.get('id')!='android:id/button2':raise RuntimeError('Unexpected cancel target')
        a.key('a')
        _,root,_,r['cancelled']=a.snap('wifi-password-cancelled',True)
        if r['cancelled']['window']!='WLAN':raise RuntimeError('Cancel did not return to WLAN')
        r['after']=adb('dumpsys wifi | grep -E "Wi-Fi is|mWifiInfo"')
        if 'SSID: Xiaomi_0421,' not in r['after'] or 'Supplicant state: COMPLETED' not in r['after']:raise RuntimeError('Original network not retained')
        r['status']='PASS_PASSWORD_EDITOR_TO_TV_KEYS_DPAD_DOWN_A_AND_CANCEL';print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:a.close();receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
