"""Check every actual binary/DEX reader of the hardware profile against policy."""
from pathlib import Path
import hashlib,json,re,zipfile
from audit_rc3_card import audit as previous_audit
HOST=Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin')
PROFILE=b'persist.vendor.rgsp.input_profile'

def audit(work,run):
 report,parent=previous_audit(work,run,'User RC4','rc4')
 policy=work/'files/vendor/etc/selinux/precompiled_sepolicy'
 old=Path('/home/lpf/roc-os-user-card-rc3-20261106-v1/files/vendor/etc/selinux/precompiled_sepolicy')
 probes=[]
 for domain in ['hal_light_default','hal_thermal_default']:
  # This negative control is the failed RC3 policy, never a deployment input.
  rule=f'neverallow {domain} roc_input_profile_prop:file read;'
  run([HOST/'sepolicy-analyze',old,'neverallow','-n',rule])
  for perm in ['read','open','getattr','map']:
   run([HOST/'sepolicy-analyze',policy,'neverallow','-n',f'neverallow {domain} roc_input_profile_prop:file {perm};'],(255,))
  run([HOST/'sepolicy-analyze',policy,'neverallow','-n',f'neverallow {domain} roc_input_profile_prop:property_service set;'])
  probes.append({'domain':domain,'old_RC3_read_denied':True,'RC4_read_open_getattr_map':True,'write_forbidden':True})
 readers={}
 for p in (work/'elf').rglob('*'):
  if p.is_file() and PROFILE in p.read_bytes():readers[p.name]='ELF'
 seen=set()
 for root in [work/'apk-catalog',work/'files']:
  for p in root.rglob('*.apk'):
   digest=hashlib.sha256(p.read_bytes()).hexdigest()
   if digest in seen:continue
   seen.add(digest)
   with zipfile.ZipFile(p) as z:
    if any(PROFILE in z.read(n) for n in z.namelist() if re.fullmatch(r'classes\d*\.dex',n)):
     readers[p.stem]='DEX'
 domains={'android.hardware.light@2.0-service.rocsource':'hal_light_default',
          'android.hardware.thermal@2.0-service.rocsource':'hal_thermal_default',
          'H700Lid':'platform_app','ROCReleaseProvisioning':'platform_app'}
 assert set(readers)==set(domains),('Unreviewed actual property consumers',readers)
 for name,domain in domains.items():
  run([HOST/'sepolicy-analyze',policy,'neverallow','-n',f'neverallow {domain} roc_input_profile_prop:file read;'],(255,))
 result={'passed':True,'actual_profile_consumers':{name:{'format':readers[name],'domain':domain,'profile_read_allowed':True} for name,domain in domains.items()},
         'all_actual_ELF_and_APK_DEX_readers_reviewed':True,'HAL_regression_controls':probes,
         'scope':'Exact profile read for all existing consumers; no property write or generic area access added',
         'runtime_first_boot_retest_required':True,'formal_release_allowed':False}
 (work/'rc4-consumer-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 report['rc4_consumer_audit']='rc4-consumer-audit.json'
 (work/'user-partition-audit.json').write_text(json.dumps(report,indent=2)+'\n')
 print('RC4_ALL_ACTUAL_PROFILE_READERS_POLICY_PASS',flush=True)
 return report,parent
