"""Bind RC3 fixes to actual property contexts and the compiled enforcing policy."""
from pathlib import Path
import json
from audit_rc2_card import audit as audit_boot
REPO=Path(__file__).resolve().parents[2]
HOST=Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin')

def audit(work,run,expected_marker='User RC3',candidate='rc3'):
 report,parent=audit_boot(work,run,expected_marker,candidate)
 policy=work/'files/vendor/etc/selinux/precompiled_sepolicy'
 checks=[]
 def check(domain,typ,kind,perm,allowed):
  rule=f'neverallow {domain} {typ}:{kind} {perm};'
  p=run([HOST/'sepolicy-analyze',policy,'neverallow','-n',rule],(255 if allowed else 0,))
  checks.append({'domain':domain,'type':typ,'class':kind,'permission':perm,'allowed':p.returncode==255})
 for domain in ['platform_app','shell']:
  for perm in ['read','open','getattr','map']:check(domain,'roc_input_profile_prop','file',perm,True)
 check('init','roc_input_profile_prop','property_service','set',True)
 check('platform_app','roc_input_profile_prop','property_service','set',False)
 check('platform_app','vendor_default_prop','file','read',False)
 check('untrusted_app','roc_input_profile_prop','file','read',False)
 for perm in ['read','open','getattr']:check('hal_thermal_default','sysfs_thermal','file',perm,True)
 for perm in ['write','append','create','setattr']:check('hal_thermal_default','sysfs_thermal','file',perm,False)
 # Every parent in the Hall path remains traversable, the endpoint stays read-only.
 check('platform_app','sysfs_batteryinfo','dir','search',True)
 check('platform_app','sysfs_batteryinfo','lnk_file','read',True)
 check('platform_app','sysfs_batteryinfo','file','read',False)
 check('platform_app','sysfs_roc_hall','file','read',True)
 check('platform_app','sysfs_roc_hall','file','write',False)
 path=work/'actual-plat-property-contexts'
 run(['/usr/sbin/debugfs','-R','dump /system/etc/selinux/plat_property_contexts '+str(path),work/'system.raw'])
 lines=[s.split('#',1)[0].split() for s in path.read_text().splitlines() if s.split('#',1)[0].strip()]
 assert ['persist.vendor.rgsp.input_profile','u:object_r:roc_input_profile_prop:s0','exact','string'] in lines
 assert report['properties'].get('persist.vendor.rgsp.input_profile')=='rg34xxsp'
 result={'passed':True,'actual_policy_checks':checks,'exact_profile_property_mapping':True,
         'generic_vendor_property_area_still_inaccessible':True,'no_app_property_write':True,
         'CPU_existing_sysfs_thermal_read_only':True,'fresh_BOOT_COMPLETED_provisioning_retest_required':True,
         'formal_release_allowed':False}
 (work/'rc3-repair-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 report['rc3_repair_audit']='rc3-repair-audit.json'
 (work/'user-partition-audit.json').write_text(json.dumps(report,indent=2)+'\n')
 print('RC3_PROFILE_AND_CPU_THERMAL_POLICY_PASS',flush=True)
 return report,parent
