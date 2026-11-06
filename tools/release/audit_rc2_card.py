"""Validate the real RC2 files and policy against observed enforcing boot failures."""
from pathlib import Path
import hashlib,json,re
from audit_candidate_card import audit as base_audit

REPO=Path(__file__).resolve().parents[2]
HOST=Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin')

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def audit(work,run,expected_marker='User RC2',candidate='rc2'):
 lock=json.loads((REPO/'out/source64-user-candidate-20261104/result-lock.json').read_text())
 root=REPO/'android/h700-android10/device/roc/roc_os_release_candidate'
 assert {p.relative_to(REPO).as_posix() for p in root.rglob('*') if p.is_file()}==set(lock['repo_candidate_source_file_set'])
 report,parent=base_audit(work,run,expected_marker,'user_boot_init_rc2.sh')
 prepared=json.loads((REPO/'out/source64-user-candidate-20261104'/report['prepare_receipt']).read_text())
 native=Path('/home/lpf/h700-android10/android/device/roc/roc_os_release_candidate')
 for name,target in prepared.get('candidate_links',{}).items():
  p=native/name
  assert p.is_symlink() and str(p.readlink())==target,name
 files=work/'files'
 def actual(path):
  part,inside=('vendor',path[8:]) if path.startswith('/vendor/') else ('system',path.lstrip('/'))
  dest=files/part/inside
  if not dest.is_file():
   dest.parent.mkdir(parents=True,exist_ok=True)
   run(['/usr/sbin/debugfs','-R','dump /'+inside+' '+str(dest),work/(part+'.raw')])
  assert dest.is_file(),path
  return dest
 policy=actual('/vendor/etc/selinux/precompiled_sepolicy')
 checks=[]
 def permission(domain,typ,kind,perm,allowed):
  rule=f'neverallow {domain} {typ}:{kind} {perm};'
  p=run([HOST/'sepolicy-analyze',policy,'neverallow','-n',rule],(255 if allowed else 0,))
  checks.append({'domain':domain,'type':typ,'class':kind,'permission':perm,'allowed':p.returncode==255})
 for perm in ['open','read','getattr','search']:
  permission('hal_thermal_default','sysfs_roc_thermal','dir',perm,True)
 for perm in ['open','read','getattr']:
  permission('hal_thermal_default','sysfs_roc_thermal','file',perm,True)
 permission('hal_thermal_default','sysfs_roc_thermal','lnk_file','read',True)
 for perm in ['write','append','create','setattr']:
  permission('hal_thermal_default','sysfs_roc_thermal','file',perm,False)
 for perm in ['read','open']:
  permission('hal_health_default','sysfs_batteryinfo','file',perm,True)
 permission('init','vendor_file','system','module_load',True)
 permission('init','system_lib_file','system','module_load',False)
 for perm in ['open','read','write','ioctl']:
  permission('surfaceflinger','gpu_device','chr_file',perm,True)
 for perm in ['read','open']:
  permission('adbd','adb_keys_file','file',perm,True)
 permission('init','system_radio_prop','property_service','set',True)
 permission('init','configfs','file','write',True)
 # Validate Native contexts, including a negative control for the old GSI label.
 fc=work/'rc2-valid-contexts'
 fc.write_text('/data u:object_r:system_data_file:s0\n/data/misc/adb(/.*)? u:object_r:adb_keys_file:s0\n')
 run([HOST/'checkfc',policy,fc])
 bad=work/'rc2-old-invalid-context';bad.write_text('/data u:object_r:system_data_root_file:s0\n')
 p=run([HOST/'checkfc',policy,bad],(1,))
 assert 'not defined' in p.stderr
 cil=actual('/system/etc/selinux/plat_sepolicy.cil').read_text()
 for path in ['/class/thermal','/devices/virtual/thermal','/class/power_supply',
              '/devices/platform/soc/twi5/i2c-5/5-0034/axp2202-bat-power-supply.0/power_supply/axp2202-battery',
              '/devices/platform/soc/twi5/i2c-5/5-0034/axp2202-usb-power-supply.0/power_supply/axp2202-usb']:
  assert path in cil,path
 assert 'sysfs_roc_hall' in cil and '/power_supply/axp2202-battery/hallkey' in cil
 module=actual('/vendor/modules/mali_kbase.ko')
 assert sha(module)=='987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9'
 s=run(['/usr/sbin/debugfs','-R','stat /modules/mali_kbase.ko',work/'vendor.raw']).stdout
 assert 'u:object_r:vendor_file:s0' in s,s
 configs={}
 for path in ['/system/etc/init/rgsp_fix63_graphics.rc','/system/etc/init/roc-source64-startup.rc',
              '/system/etc/init/h700-usb-configfs.rc','/vendor/etc/init/roc-user-input.rc',
              '/vendor/etc/init/roc-audio-interface.rc']:
  p=actual(path);run([HOST/'host_init_verifier',p]);configs[path]=sha(p)
 gfx='\n'.join(line.split('#',1)[0] for line in actual('/system/etc/init/rgsp_fix63_graphics.rc').read_text().splitlines())
 assert 'insmod /vendor/modules/mali_kbase.ko' in gfx
 assert not any(s in gfx for s in ['mknod','service rgsp-console','start rgsp-console','wake_lock'])
 startup=actual('/system/etc/init/roc-source64-startup.rc').read_text()
 assert 'restorecon /data' in startup and 'mount devpts' not in startup
 assert 'restorecon_recursive /dev' not in actual('/vendor/etc/init/roc-user-input.rc').read_text()
 usb=actual('/system/etc/init/h700-usb-configfs.rc').read_text()
 assert usb.count('mount functionfs adb ')==1 and 'on post-fs-data\n' in usb
 assert 'service.adb.tcp.port -1' in usb and 'persist.adb.tcp.port -1' in usb
 assert 'setprop ro.adb.secure' not in usb and 'setprop ro.debuggable' not in usb
 audio=actual('/vendor/etc/init/roc-audio-interface.rc').read_text()
 assert '    override\n' in audio
 assert 'interface android.hardware.audio@5.0::IDevicesFactory default' in audio
 assert 'interface android.hardware.audio.effect@5.0::IEffectsFactory default' in audio
 old_audio=actual('/vendor/etc/init/android.hardware.audio@2.0-service.rc').read_text()
 combined=work/'audio-original-plus-override.rc';combined.write_text(old_audio+'\n'+audio)
 run([HOST/'host_init_verifier',combined])
 # No stale diagnostic overlay may reintroduce a second ConfigFS setup.
 p=run(['/usr/sbin/debugfs','-R','stat /system/etc/init/roc-usb-bootdiag1.rc',work/'system.raw'])
 assert 'File not found' in p.stderr
 assert report['properties'].get('ro.roc.user.candidate')==candidate
 result={'passed':True,'actual_policy_checks':checks,'Mali_original_SHA_preserved':sha(module),
         'Mali_vendor_file_label':True,'Native_userdata_context_valid':True,'old_GSI_context_rejected':True,
         'thermal_read_only':True,'battery_exact_genfs':True,'Hall_exact_child_retained':True,
         'audio_5_interface_override_parsed':True,'single_early_authenticated_USB_setup':True,
         'config_files':configs,'runtime_retest_required':True,'formal_release_allowed':False}
 (work/'rc2-repair-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 report['rc2_repair_audit']='rc2-repair-audit.json'
 (work/'user-partition-audit.json').write_text(json.dumps(report,indent=2)+'\n')
 print('RC2_ACTUAL_POLICY_AND_BOOT_INPUTS_PASS',flush=True)
 return report,parent
