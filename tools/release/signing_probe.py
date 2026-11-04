"""Offline production-key APK probe; verifies payload, never installs or builds images."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'tools'))
from package_h700_v6a import constrained
constrained()
OUT=REPO/'out/source64-user-candidate-20261104'
graphs=sorted(OUT.glob('graph-result-v*.json'),key=lambda p:int(re.search(r'v(\d+)',p.name)[1]))
graph=json.loads(graphs[-1].read_text());assert graph['passed']
prepared=json.loads((OUT/graph['prepare_receipt']).read_text())
native=Path('/home/lpf/h700-android10/android');user=Path(prepared['separate_output'])
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert all(sha(user/p)==h for p,h in graph['graph_sha256'].items())
assert all(sha(native/'device/roc/roc_os_release_candidate'/p)==h for p,h in prepared['candidate_files'].items())
for p,target in prepared['candidate_links'].items():
 link=native/'device/roc/roc_os_release_candidate'/p
 assert link.is_symlink() and str(link.readlink())==target
work=next(Path('/home/lpf')/('roc-os-user-signing-probe-20261104-v%d'%i) for i in range(1,100) if not (Path('/home/lpf')/('roc-os-user-signing-probe-20261104-v%d'%i)).exists());work.mkdir()
source=native/'device/roc/roc_os_release_candidate/Launcher/AT4K.apk'
assert sha(source)==prepared['launcher_source_sha256']
ninja=native/'prebuilts/build-tools/linux-x86/bin/ninja'
target=user/'target/product/roc_os_source64/system/priv-app/ROCReleaseLauncher/AT4K.apk'
plan=subprocess.check_output([str(ninja),'-f',str(user/'combined-roc_os_release_candidate.ninja'),'-t','commands',str(target)],cwd=native,text=True)
(work/'launcher-command-plan.private.txt').write_text(plan)
assert 'device/roc/roc_os_release_candidate/.private-signing/platform.pk8' in plan
assert 'device/roc/roc_os_release_candidate/Launcher/AT4K.apk' in plan
key=Path('/home/lpf/.roc-os/keys/production-v1')
java=native/'prebuilts/jdk/jdk9/linux-x86/bin/java'
tool=native/'prebuilts/sdk/tools/linux/lib/apksigner.jar'
signed=work/'AT4K-production-platform.apk'
def run(args):
 p=subprocess.run(list(map(str,args)),capture_output=True,text=True)
 if p.returncode:raise RuntimeError('APK probe command failed: '+p.stderr)
 return p.stdout
run([java,'-Xmx256m','-jar',tool,'sign','--min-sdk-version','29','--key',key/'platform.pk8','--cert',key/'platform.x509.pem','--out',signed,source])
verification=run([java,'-Xmx256m','-jar',tool,'verify','--min-sdk-version','29','--max-sdk-version','29','--verbose','--print-certs',signed])
(work/'verification.txt').write_text(verification)
identity=json.loads((key/'generation-complete.public.json').read_text())
assert re.findall(r'certificate SHA-256 digest: (\w+)',verification)==[identity['roles']['platform']['certificate_sha256']]
run([Path('/home/lpf/roc-os-source64-20261103/out/host/linux-x86/bin/zipalign'),'-c','4',signed])
def payload(p):
 with zipfile.ZipFile(p) as z:
  assert len(z.namelist())==len(set(z.namelist()))
  return {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC)|SIG-[^/]+)',n,re.I)}
assert payload(source)==payload(signed),'APK payload changed'
report={'passed':True,'source_graph_receipt':graphs[-1].name,'source_prepare_receipt':graph['prepare_receipt'],
 'source_APK_sha256':sha(source),'production_signed_APK_sha256':sha(signed),
 'platform_certificate_sha256':identity['roles']['platform']['certificate_sha256'],
 'actual_Ninja_plan_selects_private_platform_key':True,'Android10_signature_verification':True,
 'zipalign_check':True,'all_non_signature_ZIP_members_unchanged':True,'payload_member_count':len(payload(source)),
 'source_original_APK_unchanged':sha(source)==prepared['launcher_source_sha256'],
 'installed_on_device':False,'actual_user_make_APK_compiled':False,'Android_images_compiled':False,
 'formal_release_accepted':False}
receipt=next(OUT/('signing-probe-v%d.json'%i) for i in range(1,100) if not (OUT/('signing-probe-v%d.json'%i)).exists());receipt.write_text(json.dumps(report,indent=2)+'\n')
print('PRODUCTION_KEY_APK_SIGN_VERIFY_PAYLOAD_AND_ALIGNMENT_PASS; NOT_INSTALLED')
