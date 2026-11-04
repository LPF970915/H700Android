"""Resource-capped release preparation. No ADB, block device or image packaging."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from package_h700_v6a import constrained
constrained()
import audit_release,inventory
OUT=ROOT/'out/source64-release-prep-20261104';OUT.mkdir(exist_ok=True)
run=next(OUT/('run-v%d'%i) for i in range(1,100) if not (OUT/('run-v%d'%i)).exists());run.mkdir()
def sha(p):return inventory.sha(p)
if sys.argv[1]=='H700SourceInventory':
 source=Path('/home/lpf/h700-android10/android');report=inventory.inventory(source,run/'source-files.jsonl');report['source']='retained Android10 BSP tree';report['scope']='content snapshot, not reconstructed upstream repo commits';report['native_repo_manifest_exists']=(source/'.repo/manifest.xml').exists();report['toolchain_and_vendor_inputs_included']=True
 parent=ROOT/'out/roc-os-source64-round2-20261103';built=json.loads((parent/'images-result-v17.json').read_text());prepared=json.loads((parent/built['prepare_receipt']).read_text());report['protected_371_inputs_match']=all(sha(source/p)==v for p,v in prepared['protected_native_sha256'].items());report['isolated_ABI5_libraries_match']=all(sha(Path('/home/lpf/roc-os-source64-20261103/host-compat/lib')/p)==v for p,v in prepared['host_compat_library_sha256'].items());report['build_receipt']='images-result-v17.json';report['prepare_receipt']=built['prepare_receipt'];report['whole_source_upstream_manifest_complete']=False
 (run/'inventory-result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
else:
 tests=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tools/release'),'-p','test_release_tools.py','-v'],capture_output=True,text=True,env={**os.environ,'ROC_RELEASE_TEST_FIXTURES':'/home/lpf/roc-release-prep-20261104/'+run.name});(run/'tests.log').write_text(tests.stdout+tests.stderr);print(tests.stderr,flush=True);assert tests.returncode==0
 work=Path('/home/lpf/roc-os-source64-20261103/round2-audit-v12');props,rc,loaded=audit_release.snapshot(work)
 # Read the frozen boot header only; no partition/disk operations.
 image=Path('/home/lpf/roc-os-source64-card-20261104-v1/ROC_OS_ARM64_Source64_Clean_Test1_20261104.img')
 with image.open('rb') as f:f.seek(155189248);h=f.read(1632)
 assert h[:8]==b'ANDROID!';cmdline=(h[64:576].split(b'\0')[0]+b' '+h[608:1632].split(b'\0')[0]).decode()
 report=audit_release.evaluate(props,rc,cmdline)
 import recovery
 actual_geometry=recovery.geometry(image)
 report['actual_frozen_seed_geometry_passed']=actual_geometry
 report.update(tests_passed=True,tests_run=10,actual_snapshot='round2-audit-v12',properties=props,property_files=loaded,scope='actual engineering build is deliberately blocked; no device/security mode changed',kernel_user_SELinux_unvalidated=True)
 # Freeze external binary identities without distributing their bytes.
 contract=json.loads((ROOT/'out/roc-os-source64-round2-20261103/boot-contract.json').read_text())
 prefix=Path('/home/lpf/h700-dualabi-image-20261031/prefix.candidate.raw')
 assert sha(prefix)==contract['prefix_sha256']
 meta=json.loads((work/'files.json').read_text());components=[]
 for name,v in meta.items():
  if not v.get('exists') or not (name.endswith('.apk') or name.endswith('.ko') or 'libGLES_mali.so' in name):continue
  components.append({'artifact_path':name,'sha256':v['sha256'],'bytes':v['bytes'],'redistribution_review':'not_accepted'})
 external={'schema':1,'boot_prefix_sha256':contract['prefix_sha256'],'kernel_DTB':'retained binary, not rebuilt by Android source target','APK_and_vendor_components':components,'selected_APK_signers':json.loads((work/'result.json').read_text())['signers'],'licenses_accepted':False,'keys':'public fingerprints only; no private keys generated'}
 (run/'external-inputs.json').write_text(json.dumps(external,indent=2)+'\n')
 latest=OUT/'latest-inventory.json'
 if latest.exists():
  ip=Path(json.loads(latest.read_text())['work']);ir=json.loads((ip/'inventory-result.json').read_text());assert sha(ip/'source-files.jsonl')==ir['sha256']
  # The archived source has no upstream repo lock. External symlink payloads
  # have not been inventoried; report that closure gap rather than hide it.
  external_links=0
  with (ip/'source-files.jsonl').open() as stream:
   for line in stream:
    row=json.loads(line)
    if row['type']!='symlink':continue
    target=row['target'];resolved=os.path.normpath(os.path.join('/home/lpf/h700-android10/android',os.path.dirname(row['path']),target))
    if not resolved.startswith('/home/lpf/h700-android10/android/'):external_links+=1
  ir.update(unhashed_lexically_external_symlinks=external_links,symlinks_followed=False,root_out_excluded=True,reference_Longan_not_compiled_or_inventoried=True,atomic_filesystem_snapshot=False,complete_upstream_manifest=False)
  (run/'inventory-summary.json').write_text(json.dumps(ir,indent=2)+'\n')
 (run/'release-readiness.json').write_text(json.dumps(report,indent=2)+'\n');assert not report['release_allowed'],'Do not certify this engineering image';print('RELEASE_TOOLS_PASS; ENGINEERING_IMAGE_BLOCKED',report['blockers'],flush=True)
(OUT/('latest-'+('inventory' if sys.argv[1]=='H700SourceInventory' else 'prep')+'.json')).write_text(json.dumps({'work':str(run)})+'\n')
