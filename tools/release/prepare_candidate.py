"""Stage an isolated user product and guarded launcher. No compile, ADB or signing."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tarfile
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
if destination.exists():
 assert marker.is_file() and marker.read_text()=='roc-user-candidate-v1\n','Refuse unknown native product'
 archive=OUT/(receipt.stem+'-previous-source.tar.gz')
 with tarfile.open(archive,'x:gz',dereference=False) as t:t.add(destination,arcname=destination.name)
else:destination.mkdir()
assert not destination.is_symlink()
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
guards()
report={'schema':1,'product':'roc_os_release_candidate-user','source_build_receipt':build.name,
 'source_audit':work.name,'protected_371_and_source64_product_unchanged':True,
 'candidate_files':{p.relative_to(destination).as_posix():sha(p) for p in sorted(destination.rglob('*')) if p.is_file()},
 'candidate_links':{'.private-signing':str(keys)},'private_key_bytes_copied_to_source':False,
 'launcher_original_retained':True,'launcher_source_sha256':sha(original),
 'platform_certificate_sha256':identity['roles']['platform']['certificate_sha256'],
 'external_backup_verified':True,'required_private_key_environment':'ROC_RELEASE_KEYS_DIR',
 'separate_output':'/home/lpf/roc-os-user-20261104/out','compiled':False,'device_accessed':False,
 'security_and_boot_acceptance':False,'whole_card_image_created':False}
receipt.write_text(json.dumps(report,indent=2)+'\n')
(OUT/'latest-prepare.json').write_text(json.dumps({'receipt':receipt.name})+'\n')
print('ISOLATED_USER_PRODUCT_PREPARED; ORIGINAL_SOURCE64_AND_LAUNCHER_RETAINED; NOT_COMPILED')
