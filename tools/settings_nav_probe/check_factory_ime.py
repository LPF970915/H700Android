"""Exercise the actual firstboot script with only LatinIME enabled, in isolated state."""
import argparse, hashlib, json, shlex, subprocess
from audit import Audit, OUT, ROOT, ADB, TARGET, adb

TV = 'com.android.inputmethod.leanback/.service.LeanbackImeService'
LATIN = 'com.android.inputmethod.latin/.LatinIME'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);args=p.parse_args()
    if not args.tag.replace('-','').isalnum():raise ValueError('Invalid tag')
    path=OUT/('factory-ime-'+args.tag+'.json')
    if path.exists():raise ValueError('Fresh tag required')
    a=Audit();r={'physical_factory_boot':False,'status':'RUNNING'};changed=False
    try:
        r['default_before']=adb('settings --user 0 get secure default_input_method').strip()
        r['enabled_before']=adb('settings --user 0 get secure enabled_input_methods').strip()
        r['home_before']=adb('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME').strip()
        if r['default_before']!=TV or 'com.overdevs.at4k/.MainActivity' not in r['home_before']:
            raise RuntimeError('Expected tested TV/AT4K baseline')
        r['installed']=adb('ime list -a -s')
        if TV not in r['installed'] or LATIN not in r['installed']:raise RuntimeError('Both IMEs required')
        source=ROOT/'android/h700-android10/device/roc/rgsp/rgsp-firstboot.sh'
        raw=source.read_bytes().replace(b'\r\n',b'\n');r['source_sha256']=hashlib.sha256(raw).hexdigest()
        base='/data/local/tmp/rgsp-firstboot-fixture-'+args.tag
        text=raw.decode().replace('state=/data/local/rgsp-firstboot','state='+base).replace('/system/etc/rgsp/leanback.sha256',base+'.sha256').replace('/system/bin/set_rgsp_home.sh',base+'-home.sh')
        r['fixture_substitutions']={'state':base,'expected_ime_sha256_file':base+'.sha256','home_helper':base+'-home.sh'}
        local=OUT/('factory-ime-'+args.tag+'.sh');local.write_bytes(text.encode())
        sha=ROOT/'android/h700-android10/device/roc/rgsp/configs/leanback.sha256'
        r['fixture_absent']=adb('test ! -e '+base+' && echo ABSENT')
        subprocess.run([ADB,'-s',TARGET,'push',str(local),base+'.sh'],check=True,capture_output=True)
        subprocess.run([ADB,'-s',TARGET,'push',str(sha),base+'.sha256'],check=True,capture_output=True)
        helper=ROOT/'tools/set_rgsp_home.sh'
        r['home_helper_sha256']=hashlib.sha256(helper.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        helper_copy=OUT/('factory-ime-'+args.tag+'-home.sh');helper_copy.write_bytes(helper.read_bytes().replace(b'\r\n',b'\n'))
        subprocess.run([ADB,'-s',TARGET,'push',str(helper_copy),base+'-home.sh'],check=True,capture_output=True)
        changed=True
        r['setup']=a.command('ime enable --user 0 '+LATIN+' && ime set --user 0 '+LATIN+' && ime disable --user 0 '+TV)
        r['fresh_enabled']=adb('ime list -s')
        if TV in r['fresh_enabled']:raise RuntimeError('TV still enabled in fresh fixture')
        r['apply']=a.command('sh '+base+'.sh apply',timeout=55)
        r['default_after']=adb('settings --user 0 get secure default_input_method').strip()
        r['enabled_after']=adb('ime list -s')
        r['marker']=adb('cat '+base+'/complete-v1').strip()
        if r['default_after']!=TV or TV not in r['enabled_after'] or not r['marker']:
            raise RuntimeError('Factory script did not provision TV IME')
        r['second_apply']=a.command('sh '+base+'.sh apply')
        if 'existing user choices preserved' not in r['second_apply']:raise RuntimeError('Completed state not respected')
        r['status']='PASS_LATIN_ONLY_FRESH_STATE_PROVISIONS_TV_IME'
        print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:
        if changed:
            # Restore the exact baseline enabled subtypes and selected IME.
            old=r['enabled_before']
            if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/:;-' for c in old):
                raise RuntimeError('Unexpected enabled IME serialization; baseline in receipt')
            r['restore']=a.command('settings --user 0 put secure enabled_input_methods '+shlex.quote(old)+'; ime set --user 0 '+shlex.quote(r['default_before']))
            r['home_after']=adb('cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME').strip()
            if r['home_after']!=r['home_before']:r['restore_home']=a.command('cmd package set-home-activity --user 0 com.overdevs.at4k/.MainActivity')
        a.close();path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
