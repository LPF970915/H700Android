"""Validate the effective first-wins BSP copy plan before user compilation."""
from pathlib import Path
import sys,json
selected={}
for item in sys.argv[1].split():
 if ':' in item:
  source,destination=item.split(':',1);selected.setdefault(destination,source)
base='device/roc/roc_os_release_candidate/configs/'
required={x:base+'retired-service.rc' for x in ['system/etc/init/h700-network-validation-defaults.rc','system/etc/init/rgsp-wallpapers.rc','vendor/etc/init/rgsp-stick-axes.rc','vendor/etc/init/rgsp-input-bringup.rc']}
required.update({'system/etc/rgsp/leanback.sha256':base+'leanback.sha256','vendor/etc/init/roc-user-input.rc':base+'roc-user-input.rc'})
for name,source in required.items():assert selected.get(name)==source,(name,selected.get(name))
defaults={}
for item in sys.argv[2].split():
 if '=' in item:
  key,value=item.split('=',1);defaults.setdefault(key,value)
assert defaults.get('persist.sys.usb.config')=='none','USB default must be first-wins none'
out=Path(__file__).resolve().parents[2]/'out/source64-user-candidate-20261104'
receipt=next(out/('effective-copy-plan-v%d.json'%i) for i in range(1,100) if not (out/('effective-copy-plan-v%d.json'%i)).exists())
receipt.write_text(json.dumps({'passed':True,'required_first_copy_sources':required},indent=2)+'\n')
print('USER_FUNCTIONAL_COPY_PLAN_PASS')
