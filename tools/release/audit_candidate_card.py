"""Audit real user partitions before assembling a local test-candidate card."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile

REPO=Path(__file__).resolve().parents[2]
NATIVE=Path('/home/lpf/h700-android10/android')
TARGET=Path('/home/lpf/roc-os-user-20261104/out/target/product/roc_os_source64')

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def audit(work,run):
 out=REPO/'out/source64-user-candidate-20261104'
 receipt=max(out.glob('images-result-v*.json'),key=lambda p:int(re.search(r'v(\d+)',p.name)[1]))
 built=json.loads(receipt.read_text());assert built['passed'] and built['exit_status']==0
 prepared=json.loads((out/built['prepare_receipt']).read_text())
 root=NATIVE/'device/roc/roc_os_release_candidate'
 assert set(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())==set(prepared['candidate_files'])
 for name,h in prepared['candidate_files'].items():assert sha(root/name)==h,name
 lock=json.loads((out/'result-lock.json').read_text())
 for name,h in lock['repo_compile_inputs_sha256'].items():assert sha(REPO/name)==h,name
 parent=REPO/'out/roc-os-source64-round2-20261103'
 eng=json.loads((parent/prepared['source_build_receipt']).read_text())
 original=json.loads((parent/eng['prepare_receipt']).read_text())
 for name,h in original['protected_native_sha256'].items():assert sha(NATIVE/name)==h,name
 for name,h in original['product_sha256'].items():assert sha(NATIVE/'device/roc/roc_os_source64'/name)==h,name
 for name,h in original['host_compat_library_sha256'].items():assert sha(Path('/home/lpf/roc-os-source64-20261103/host-compat/lib')/name)==h,name
 for name,v in eng['images'].items():assert sha(Path('/home/lpf/roc-os-source64-20261103/out/target/product/roc_os_source64')/name)==v['sha256']
 for name,v in built['images'].items():assert sha(TARGET/name)==v['sha256'],name
 host=Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin')
 for part in ['system','vendor']:
  run([host/'simg2img',TARGET/(part+'.img'),work/(part+'.raw')])
  run(['/usr/sbin/e2fsck','-f','-n',work/(part+'.raw')])
 metadata={}
 def file(name,required=True):
  part,inside=('vendor',name[7:]) if name.startswith('/vendor/') else ('system',name)
  dest=work/'files'/part/inside.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.is_file():run(['/usr/sbin/debugfs','-R','dump '+inside+' '+str(dest),work/(part+'.raw')])
  metadata[name]={'exists':dest.is_file()}
  if dest.is_file():metadata[name].update(sha256=sha(dest),bytes=dest.stat().st_size);return dest
  assert not required,name
 for name,spec in built['actual_ELF'].items():
  p=file('/'+name);h=p.read_bytes()[:20]
  assert sha(p)==spec['sha256'] and h[4]==spec['ELF_class'] and int.from_bytes(h[18:20],'little')==spec['e_machine'],name
 for name,spec in built['runtime_files'].items():assert sha(file('/'+name))==spec['sha256']
 # Include root actions as well as automatic init-directory imports.
 rootrc=work/'root-init';rootrc.mkdir()
 for source in sorted((TARGET/'root').glob('*.rc')):
  p=file('/'+source.name,False)
  if p is not None:(rootrc/source.name).write_bytes(p.read_bytes())
 sys.path.insert(0,str(REPO/'tools/source64'))
 from audit_linkage import audit as linkage_audit
 linkage=linkage_audit(work,run,file)
 (work/'linkage.json').write_text(json.dumps(linkage,indent=2)+'\n')
 assert not linkage['errors'] and not linkage['pre_apex_bootstrap_errors'],'Actual ELF dependency closure failed'
 rc='\n'.join(p.read_text() for directory in [work/'init-catalog',rootrc] for p in directory.rglob('*.rc'))
 # Stock AOSP passes a potential root context as an adbd argument even in user
 # builds. This is not a service seclabel: adbd runs in adbd, and user builds
 # compile ALLOW_ADBD_ROOT=0. Do not confuse that unused argument with exec/su.
 inspected_rc=rc.replace('service adbd /system/bin/adbd --root_seclabel=u:r:su:s0',
                         'service adbd /system/bin/adbd')
 assert not re.search(r'\bu:r:su:', '\n'.join(x.split('#',1)[0] for x in inspected_rc.splitlines())),'su startup domain remains'
 assert not re.search(r'^\s*(?:start|exec_start)\s+(?:rgsp-kmsg-bounded|rgsp-wallpapers|h700-network-validation-defaults)\s*$',rc,re.M)
 props={}
 for name in ['/system/etc/prop.default','/prop.default','/default.prop','/system/build.prop','/vendor/default.prop','/vendor/build.prop','/system/product/build.prop']:
  p=file(name,False)
  if p is None:continue
  for line in p.read_text().splitlines():
   if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);props[k.strip()]=v.strip()
 assert all(props.get(k)==v for k,v in {'ro.secure':'1','ro.adb.secure':'1','ro.debuggable':'0','ro.build.type':'user','persist.sys.usb.config':'none'}.items()),props
 # AOSP labels direct source builds with non-default private keys dev-keys;
 # release-keys is a later signed-target-files release step. This artifact is
 # a test candidate. Actual certificate verification below remains mandatory.
 assert props.get('ro.build.tags') in ['dev-keys','release-keys']
 variables=json.loads(Path('/home/lpf/roc-os-user-20261104/out/soong/soong.variables').read_text())
 assert not variables.get('Debuggable') and not variables.get('Eng'),'Debuggable native compilation is forbidden'
 for name in ['/system/bin/su','/system/xbin/su','/system/app/Superuser/Superuser.apk']:
  assert file(name,False) is None,'Root helper present in user image'
 for name in ['/system/priv-app/CtsShimPrivPrebuilt/CtsShimPrivPrebuilt.apk','/system/app/CtsShimPrebuilt/CtsShimPrebuilt.apk']:
  assert file(name,False) is None,'Retired CTS test shim remains inside actual filesystem'
 assert 'User RC1' in file('/system/etc/roc-user-build.txt').read_text()
 # AOSP keeps an explicitly disabled shell-UID console behind ro.debuggable=1.
 # It must never be a root console or have an unconditional start action.
 console=re.search(r'^service console .*?(?=^\S|\Z)',rc,re.M|re.S)
 if console:assert '    user shell' in console[0] and '    disabled' in console[0],console[0]
 for action in re.split(r'(?=^on )',rc,flags=re.M):
  if re.search(r'^\s+start console\s*$',action,re.M):assert action.startswith('on property:ro.debuggable=1'),action[:150]
 assert file('/system/product/etc/selinux/product_mac_permissions.xml',False) is None,'Retired product MAC map leaked into image'
 # AOSP still emits the empty-input digest when no product policy is selected.
 # It is valid only with its matching vendor digest and no product CIL/mapping.
 empty=hashlib.sha256(b'').hexdigest()
 for name in ['/system/product/etc/selinux/product_sepolicy_and_mapping.sha256',
              '/vendor/etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256']:
  assert file(name).read_text().strip()==empty,'Unexpected product policy digest'
 for name in ['/system/product/etc/selinux/product_sepolicy.cil','/system/product/etc/selinux/mapping/29.0.cil']:
  assert file(name,False) is None,'Unexpected artificial product policy remains'
 policy=file('/vendor/etc/selinux/precompiled_sepolicy')
 result=run([host/'sepolicy-analyze',policy,'permissive']);assert not result.stdout.strip(),'Permissive domains in compiled user policy'
 cil=file('/system/etc/selinux/plat_sepolicy.cil').read_text()
 assert 'sysfs_roc_hall' in cil and '/power_supply/axp2202-battery/hallkey' in cil,'Hall genfs policy missing from actual image'
 for path in ['system/app','system/priv-app','system/product/app','system/product/priv-app','system/product_services/app','system/product_services/priv-app','vendor/app','vendor/priv-app','vendor/odm/app','vendor/odm/priv-app']:
  part='vendor' if path.startswith('vendor/') else 'system';inside='/'+path[7:] if part=='vendor' else '/'+path
  dest=work/'apk-catalog'/part/path.replace('/','_');dest.mkdir(parents=True)
  run(['/usr/sbin/debugfs','-R','rdump '+inside+' '+str(dest),work/(part+'.raw')])
 identity=json.loads(Path('/home/lpf/.roc-os/keys/production-v1/generation-complete.public.json').read_text())
 roles={v['certificate_sha256'] for v in identity['roles'].values()};platform=identity['roles']['platform']['certificate_sha256']
 for role,pin in identity['roles'].items():
  cert=subprocess.check_output(['openssl','x509','-in','/home/lpf/.roc-os/keys/production-v1/'+role+'.x509.pem','-outform','DER'])
  pub=subprocess.check_output(['openssl','pkey','-inform','DER','-in','/home/lpf/.roc-os/keys/production-v1/'+role+'.pk8','-pubout','-outform','DER'])
  assert hashlib.sha256(cert).hexdigest()==pin['certificate_sha256'] and hashlib.sha256(pub).hexdigest()==pin['public_key_sha256']
 eng_audit=json.loads((parent/'round2-audit-v13.json').read_text());eng_work=Path(eng_audit['work'])
 old_apks={sha(p) for p in (eng_work/'files').rglob('*.apk')}
 # The actual filesystem directory catalog catches stale APKs even when their
 # staging files were retired. Also cover framework-res and unusual paths.
 apks=list((work/'apk-catalog').rglob('*.apk'))
 known={(p.name,sha(p)) for p in apks}
 for part in ['system','vendor']:
  for p in sorted((TARGET/part).rglob('*.apk')):
   item=file('/'+p.relative_to(TARGET).as_posix())
   if (item.name,sha(item)) not in known:apks.append(item);known.add((item.name,sha(item)))
 assert len(apks)>=20
 signers={};presigned=[];badging={};signature_errors=[]
 for p in apks:
  verify=run([NATIVE/'prebuilts/jdk/jdk9/linux-x86/bin/java','-Xmx256m','-jar',NATIVE/'prebuilts/sdk/tools/linux/lib/apksigner.jar','verify','--min-sdk-version','29','--max-sdk-version','29','--print-certs',p],(0,1))
  if verify.returncode:
   signature_errors.append({'APK':p.name,'sha256':sha(p),'error':verify.stderr[-1600:]});continue
  certs=re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)',verify.stdout)
  if not (certs and (set(certs)<=roles or sha(p) in old_apks)):
   signature_errors.append({'APK':p.name,'sha256':sha(p),'unknown_certificates':certs});continue
  if not set(certs)<=roles:presigned.append({'name':p.name,'sha256':sha(p),'certificates':certs,'license_acceptance':False})
  assert p.stem not in signers,('Duplicate APK basename',p)
  signers[p.stem]=certs
  if p.stem in ['ROCReleaseProvisioning','LeanbackIME']:badging[p.stem]=run([host/'aapt2','dump','badging',p]).stdout
 (work/'APK-signature-review.json').write_text(json.dumps({'checked':len(apks),'errors':signature_errors,'signers':signers,'retained_presigned':presigned},indent=2)+'\n')
 assert not signature_errors,('APK signature errors; see APK-signature-review.json',[x['APK'] for x in signature_errors])
 for name in ['SystemUI','Settings','ROCNavigation','H700Lid','H700Rotation','AT4K','ROCReleaseProvisioning']:
  assert signers.get(name)==[platform],('Platform app not signed by ROC platform',name,signers.get(name))
 assert 'ROCProvisioning' not in signers,'Old provisioning duplicate remains'
 keyboard=next(p for p in apks if p.stem=='LeanbackIME')
 assert sha(keyboard)==file('/system/etc/rgsp/leanback.sha256').read_text().strip(),'Signed keyboard pin mismatch'
 setup=next(p for p in apks if p.stem=='ROCReleaseProvisioning')
 manifest=run([host/'aapt2','dump','xmltree',setup,'--file','AndroidManifest.xml']).stdout
 assert 'android.permission.WRITE_SECURE_SETTINGS' in manifest and 'android.intent.action.BOOT_COMPLETED' in manifest
 with zipfile.ZipFile(setup) as archive:
  dex=b''.join(archive.read(n) for n in archive.namelist() if re.fullmatch(r'classes\d*\.dex',n))
  assert b'captive_portal_https_url' in dex and b'Wallpaper hash mismatch' in dex,'Migrated provisioning code missing'
 for phrase in ['android.permission.READ_EXTERNAL_STORAGE','android.permission.WRITE_EXTERNAL_STORAGE']:
  assert phrase in file('/system/etc/default-permissions/default-permissions-roc-setup.xml').read_text()
 boot=(REPO/'tools/release/user_boot_init.sh').read_text();module=file('/vendor/modules/h700_stick_axes.ko')
 assert sha(module) in boot and 'insmod /android-root/vendor/modules/h700_stick_axes.ko profile=rg34xxsp' in boot
 assert 'exec /bin/ash' not in boot and 'chown 0:1004 "$node"' in boot
 (work/'files.json').write_text(json.dumps(metadata,indent=2)+'\n')
 report={'passed':True,'build_receipt':receipt.name,'prepare_receipt':built['prepare_receipt'],'images':built['images'],'work':str(work),'APK_count':len(apks),'signers':signers,'retained_presigned_identity':presigned,'properties':props,'source_build_tag_requires_formal_release_step':props.get('ro.build.tags')=='dev-keys','no_su_startup_services':True,'stock_adbd_root_context_argument_is_not_a_su_service':True,'native_Debuggable':False,'no_permissive_policy_domains':True,'default_keyboard_actual_signed_hash_matches':True,'namespace_closure':{k:v for k,v in linkage.items() if k not in ['objects','graph','roots']},'runtime_acceptance':False,'formal_release_allowed':False}
 (work/'user-partition-audit.json').write_text(json.dumps(report,indent=2)+'\n')
 print('USER_PARTITION_AUDIT_PASS APKs',len(apks),flush=True)
 return report,eng_audit
