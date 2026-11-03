"""Run the selected factory shell with mock Android commands, without ADB."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

MOCK = '''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['ROC_FACTORY_MOCK']); s=json.loads(p.read_text()); name=Path(sys.argv[0]).name; a=sys.argv[1:]; out=''; rc=0
s['calls'].append([name]+a)
if name=='getprop':out=s['props'].get(a[0],'')
elif name=='id':out='0'
elif name=='am':out='0'
elif name=='pm':
 if a[0]=='path':out='package:'+s['apk']
 elif a[0]=='set-home-activity':s['home']=a[-1]
elif name=='cmd':
 if a[:2]==['role','add-role-holder']:s['home_role']=a[-2]
 else:out=s.get('home','com.android.launcher3/.Launcher')
elif name=='ime':
 if a[0]=='list':out='com.android.inputmethod.leanback/.service.LeanbackImeService'
 elif a[0]=='set':s['settings']['secure.default_input_method']=a[-1]
elif name=='settings':
 if a[0]=='--user':a=a[2:]
 op,namespace,key=a[:3]; k=namespace+'.'+key
 if op=='get':out=s['settings'].get(k,'null')
 elif op=='put':
  if s.get('fail_once')==key:s.pop('fail_once');rc=9
  else:s['settings'][k]=a[3]
p.write_text(json.dumps(s));print(out) if out else None
sys.exit(rc)
'''


def checks(product, work):
    root = work / 'factory'
    root.mkdir()
    tools = root / 'bin'; tools.mkdir()
    for name in ['getprop', 'id', 'am', 'pm', 'cmd', 'ime', 'settings']:
        f = tools / name; f.write_text(MOCK); f.chmod(0o755)
    apk = root / 'keyboard.fixture'; apk.write_bytes(b'keyboard-fixture')
    sha = root / 'keyboard.sha256'; sha.write_text(hashlib.sha256(apk.read_bytes()).hexdigest()+'\n')
    script = (product / 'configs/roc-factory.sh').read_text()
    script = script.replace('export PATH=/system/bin:/vendor/bin', 'export PATH='+str(tools)+':/usr/bin:/bin')
    script = script.replace('/system/etc/rgsp/leanback.sha256', str(sha))
    state_file = root / 'mock.json'
    env = dict(os.environ, ROC_FACTORY_MOCK=str(state_file))
    shell = shutil.which('mksh') or '/bin/sh'
    results = []
    def case(name, properties=None, existing=None, fail=None):
        folder = root / name; folder.mkdir()
        local = folder / 'factory.sh'
        local.write_text(script.replace('/data/local/roc-factory-v1', str(folder/'state')))
        s = dict(props={'ro.product.device':'rgsp', 'persist.vendor.rgsp.input_profile':'rg34xxsp',
                        'ro.roc.source64.round':'2', 'sys.boot_completed':'1'},
                 apk=str(apk), settings=existing or {}, calls=[])
        if properties:s['props'].update(properties)
        if fail:s['fail_once']=fail
        state_file.write_text(json.dumps(s))
        p = subprocess.run([shell, str(local)], env=env, capture_output=True, text=True)
        (folder/'first.log').write_text(p.stdout+p.stderr)
        return folder, local, p.returncode, json.loads(state_file.read_text())
    folder, local, rc, s = case('fresh', existing={'secure.enabled_accessibility_services':'other/.Service'})
    assert rc==0 and (folder/'state/complete').is_file()
    assert s['home']=='com.overdevs.at4k/.MainActivity'
    assert s['home_role']=='com.overdevs.at4k'
    assert s['settings']['secure.show_ime_with_hard_keyboard']=='1'
    assert s['settings']['global.device_provisioned']=='1'
    assert s['settings']['secure.enabled_accessibility_services']=='other/.Service:com.roc.rgsp.navtrial/.NavigationService'
    results.append('factory-clean-data-defaults-and-existing-accessibility-retained')
    s['settings']['secure.default_input_method']='user.keyboard/.IME'
    s['settings']['secure.enabled_accessibility_services']='user/.Service'
    s['home']='user.launcher/.Home';s['calls']=[];state_file.write_text(json.dumps(s))
    p = subprocess.run([shell, str(local)], env=env, capture_output=True, text=True)
    after = json.loads(state_file.read_text())
    assert p.returncode==0 and after['settings']==s['settings'] and after['home']==s['home']
    results.append('factory-complete-marker-preserves-user-choices')
    folder, local, rc, s = case('interrupted', fail='accessibility_enabled')
    assert rc!=0 and not (folder/'state/complete').exists()
    # The inherited kernel flock releases on shell exit; restart finishes once.
    p = subprocess.run([shell, str(local)], env=env, capture_output=True, text=True)
    s = json.loads(state_file.read_text())
    assert p.returncode==0 and (folder/'state/complete').is_file()
    assert s['settings']['secure.enabled_accessibility_services'].count('com.roc.rgsp.navtrial/.NavigationService')==1
    results.append('factory-interruption-retry-and-kernel-lock-release')
    for name, props in [('wrong-device',{'ro.product.device':'other'}),('wrong-image',{'ro.roc.source64.round':'1'})]:
        folder, _, rc, s = case(name, properties=props)
        assert rc!=0 and not (folder/'state/complete').exists() and not s['settings']
        results.append('factory-reject-'+name)
    return results
