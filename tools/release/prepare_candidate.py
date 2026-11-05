"""Stage an isolated user product and guarded launcher. No compile, ADB or signing."""
from pathlib import Path
import configparser,hashlib,json,os,shutil,subprocess,sys,tarfile,xml.etree.ElementTree as ET
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools'))
from package_h700_v6a import constrained
from build_receipts import current_audit
constrained()
NATIVE=Path('/home/lpf/h700-android10/android')
OUT=REPO/'out/source64-user-candidate-20261104';OUT.mkdir(exist_ok=True)
build,built,work=current_audit(REPO/'out/roc-os-source64-round2-20261103')
prepared=json.loads((build.parent/built['prepare_receipt']).read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def guards():
 assert all(sha(NATIVE/p)==h for p,h in prepared['protected_native_sha256'].items())
 assert all(sha(NATIVE/'device/roc/roc_os_source64'/p)==h for p,h in prepared['product_sha256'].items())
 assert all(sha(Path('/home/lpf/roc-os-source64-20261103/host-compat/lib')/p)==h for p,h in prepared['host_compat_library_sha256'].items())
guards()
keys=Path('/home/lpf/.roc-os/keys/production-v1')
identity=json.loads((keys/'generation-complete.public.json').read_text())
assert set(identity['roles'])=={'releasekey','platform','shared','media','networkstack'}
backup=json.loads((REPO/'out/source64-release-run-20261104/external-key-backup.public.json').read_text())
assert backup['external_backup_decrypt_verified'] and backup['backup_sha256']==identity['backup_sha256']
for role,pin in identity['roles'].items():
 cert=subprocess.check_output(['openssl','x509','-in',str(keys/(role+'.x509.pem')),'-outform','DER'])
 assert hashlib.sha256(cert).hexdigest()==pin['certificate_sha256']
 pub=subprocess.check_output(['openssl','pkey','-inform','DER','-in',str(keys/(role+'.pk8')),'-pubout','-outform','DER'])
 assert hashlib.sha256(pub).hexdigest()==pin['public_key_sha256']
source=REPO/'android/h700-android10/device/roc/roc_os_release_candidate'
destination=NATIVE/'device/roc/roc_os_release_candidate'
marker=destination/'.roc-owned-candidate'
receipt=next(OUT/('prepare-v%d.json'%i) for i in range(1,100) if not (OUT/('prepare-v%d.json'%i)).exists())
receipt.write_text(json.dumps({'passed':False,'incomplete':True,'stage':'preparing'})+'\n')
if destination.exists():
 assert marker.is_file() and marker.read_text()=='roc-user-candidate-v1\n','Refuse unknown native product'
 archive=OUT/(receipt.stem+'-previous-source.tar.gz')
 with tarfile.open(archive,'x:gz',dereference=False) as t:t.add(destination,arcname=destination.name)
else:destination.mkdir()
assert not destination.is_symlink()
# Retire the reviewed empty-product-CIL workaround after preserving the full
# owned-source tar above. It is unnecessary on the platform-private keymap route.
retired=destination/'sepolicy/private/attributes'
if retired.exists():
 assert retired.is_file() and not retired.is_symlink()
 assert sha(retired)=='fd7984c92868d9ba52cd366cf2107971738012b33fd018ca6d6f1e81dd656ce7'
 shutil.copyfile(retired,OUT/(receipt.stem+'-retired-product-attributes'))
 retired.unlink()
# Retire only the exact reviewed candidate-only abandoned keyboard genrule.
# The full source tar above preserves it without dereferencing private keys.
retired_bp=destination/'Android.bp'
if retired_bp.exists():
 assert retired_bp.is_file() and not retired_bp.is_symlink()
 assert sha(retired_bp)=='7a490afb5d3d19dd8d313e1a186644dcf2ac1e2420c856e99e9a44de6a2115dc'
 shutil.copyfile(retired_bp,OUT/(receipt.stem+'-retired-keyboard-genrule.bp'))
 retired_bp.unlink()
for p in source.rglob('*'):
 if p.is_dir():continue
 assert p.is_file() and not p.is_symlink()
 target=destination/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
 assert not target.is_symlink()
 if not target.exists() or target.read_bytes()!=p.read_bytes():shutil.copyfile(p,target)
original=NATIVE/'device/roc/rgsp/prebuilt/AT4K/AT4K.apk'
audited=next(p for p in (work/'files').rglob('AT4K.apk'))
assert sha(original)==sha(audited),'Retained launcher differs from accepted image'
target=destination/'Launcher/AT4K.apk'
if target.exists():assert sha(target)==sha(original),'Refuse unknown launcher replacement'
else:shutil.copyfile(original,target)
link=destination/'.private-signing'
if link.is_symlink():assert link.readlink()==keys,'Private signing link changed'
else:
 assert not link.exists(),'Refuse unknown signing directory'
 link.symlink_to(keys,target_is_directory=True)
marker.write_text('roc-user-candidate-v1\n')

# Validate the real BSP certificate substitution tool once it has been built.
# ConfigParser merges this product-only USER override after the stock mapping.
mac_probe={'executed':False,'reason':'user insertkeys tool not built yet'}
insert=Path('/home/lpf/roc-os-user-20261104/out/host/linux-x86/bin/insertkeys.py')
if insert.is_file():
 probe=OUT/(receipt.stem+'-mac-probe');probe.mkdir()
 merged=probe/'keys.conf'
 with merged.open('wb') as f:
  subprocess.run(['m4','--fatal-warnings','-s',str(NATIVE/'system/sepolicy/private/keys.conf'),
    str(destination/'sepolicy/private/keys.conf')],stdout=f,check=True)
 parser=configparser.ConfigParser(strict=False);parser.read(merged)
 assert parser.get('@RELEASE','user')=='device/roc/roc_os_release_candidate/.private-signing/releasekey.x509.pem'
 env={**os.environ,'DEFAULT_SYSTEM_DEV_CERTIFICATE':str(link)}
 output=probe/'plat_mac_permissions.xml'
 python2=NATIVE/'prebuilts/build-tools/path/linux-x86/python'
 result=subprocess.run([str(python2),str(insert),'-t','user','-c',str(NATIVE),str(merged),'-o',str(output),
   str(NATIVE/'system/sepolicy/private/mac_permissions.xml')],capture_output=True,text=True,env=env)
 (probe/'insertkeys.log').write_text(result.stdout+result.stderr)
 assert result.returncode==0,'Actual insertkeys preflight failed; see local probe log'
 signers={hashlib.sha256(bytes.fromhex(s.attrib['signature'])).hexdigest()
   for s in ET.parse(output).getroot().iter('signer')}
 assert signers and signers <= {v['certificate_sha256'] for v in identity['roles'].values()}
 assert identity['roles']['platform']['certificate_sha256'] in signers
 # Product policy has its own empty XML template and no DEFAULT_* environment.
 # Its certificate map must resolve without introducing signer grants.
 product_output=probe/'product_mac_permissions.xml'
 product_env=dict(os.environ);product_env.pop('DEFAULT_SYSTEM_DEV_CERTIFICATE',None)
 result=subprocess.run([str(python2),str(insert),'-t','user','-c',str(NATIVE),
   str(destination/'sepolicy/private/keys.conf'),'-o',str(product_output),
   str(NATIVE/'system/sepolicy/reqd_mask/mac_permissions.xml')],capture_output=True,text=True,env=product_env)
 (probe/'product-insertkeys.log').write_text(result.stdout+result.stderr)
 assert result.returncode==0,'Product insertkeys preflight failed'
 assert not list(ET.parse(product_output).getroot().iter('signer'))
 mac_probe={'executed':True,'actual_insertkeys_passed':True,'release_USER_points_to_production_releasekey':True,
  'output_sha256':sha(output),'signer_certificate_sha256':sorted(signers),
  'product_empty_policy_no_extra_signer_grants':True,'product_output_sha256':sha(product_output)}

# A certificate map belongs to the platform-private input. Enabling a product
# policy for it creates empty product CIL/mapping files in this old BSP.
assert sorted(p.name for p in (destination/'sepolicy/private').iterdir())==['genfs_contexts','keys.conf','roc_hall.te']
policy_route={'certificate_map_only':False,'candidate_Hall_read_only_policy':True,'unused_product_attribute_retired':True,
 'expected_board_private_directories':['device/softwinner/common/sepolicy/private',
                                     'device/roc/roc_os_release_candidate/sepolicy/private'],
 'expected_product_public_and_private_directories':[],
 'real_build_route_guard_required':True}

guards()
report={'schema':1,'passed':True,'incomplete':False,'product':'roc_os_release_candidate-user','source_build_receipt':build.name,
 'source_audit':work.name,'protected_371_and_source64_product_unchanged':True,
 'candidate_files':{p.relative_to(destination).as_posix():sha(p) for p in sorted(destination.rglob('*')) if p.is_file()},
 'candidate_links':{'.private-signing':str(keys)},'private_key_bytes_copied_to_source':False,
 'launcher_original_retained':True,'launcher_source_sha256':sha(original),
 'platform_certificate_sha256':identity['roles']['platform']['certificate_sha256'],
 'external_backup_verified':True,'required_private_key_environment':'ROC_RELEASE_KEYS_DIR',
 'platform_mac_permissions_preflight':mac_probe,
 'certificate_policy_route':policy_route,
 'separate_output':'/home/lpf/roc-os-user-20261104/out','compiled':False,'device_accessed':False,
 'security_and_boot_acceptance':False,'whole_card_image_created':False}
receipt.write_text(json.dumps(report,indent=2)+'\n')
(OUT/'latest-prepare.json').write_text(json.dumps({'receipt':receipt.name})+'\n')
print('ISOLATED_USER_PRODUCT_PREPARED; ORIGINAL_SOURCE64_AND_LAUNCHER_RETAINED; NOT_COMPILED')
