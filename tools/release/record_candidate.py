"""Record isolated user graph status and protected inputs, including failures."""
from pathlib import Path
import hashlib,json,sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'tools'))
from package_h700_v6a import constrained
constrained()
OUT=REPO/'out/source64-user-candidate-20261104'
phase=sys.argv[2] if len(sys.argv)>2 else 'graph'
assert phase in {'graph','images'}
latest=json.loads((OUT/'latest-prepare.json').read_text())['receipt']
prepared=json.loads((OUT/latest).read_text())
native=Path('/home/lpf/h700-android10/android')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert all(sha(native/'device/roc/roc_os_release_candidate'/p)==h for p,h in prepared['candidate_files'].items())
for p,target in prepared.get('candidate_links',{}).items():
 link=native/'device/roc/roc_os_release_candidate'/p
 assert link.is_symlink() and str(link.readlink())==target
parent=REPO/'out/roc-os-source64-round2-20261103'
built=json.loads((parent/prepared['source_build_receipt']).read_text())
source=json.loads((parent/built['prepare_receipt']).read_text())
assert all(sha(native/p)==h for p,h in source['protected_native_sha256'].items())
assert all(sha(native/'device/roc/roc_os_source64'/p)==h for p,h in source['product_sha256'].items())
old=Path('/home/lpf/roc-os-source64-20261103/out/target/product/roc_os_source64')
assert all(sha(old/p)==v['sha256'] for p,v in built['images'].items())
out=Path(prepared['separate_output']);status=int(sys.argv[1])
graphs={p.relative_to(out).as_posix():sha(p) for p in out.glob('*.ninja') if p.is_file()}
images={};elf={}
artifact_error=None;runtime_files={}
if phase=='images' and status==0:
 try:
  target=out/'target/product/roc_os_source64'
  for name in ['system.img','vendor.img','ramdisk.img']:
   p=target/name;assert p.is_file() and p.stat().st_size>0,name
   images[name]={'bytes':p.stat().st_size,'sha256':sha(p)}
  expected_elf={'system/bin/app_process64':(2,183),'system/bin/app_process32':(1,40),
                'system/lib64/libandroid_runtime.so':(2,183),'system/lib/libandroid_runtime.so':(1,40),
                'vendor/lib64/hw/gralloc.rocsource.so':(2,183),'vendor/lib/hw/gralloc.rocsource.so':(1,40)}
  required=list(expected_elf)+['system/framework/wifi-service.rocsource.jar']
  missing=[name for name in required if not (target/name).is_file() or (target/name).stat().st_size==0]
  assert not missing,'Missing required runtime artifacts: '+', '.join(missing)
  for name,(bits,machine) in expected_elf.items():
   p=target/name
   with p.open('rb') as f:header=f.read(20)
   assert header[:5]==b'\x7fELF'+bytes([bits]) and header[5]==1,name
   assert int.from_bytes(header[18:20],'little')==machine,name
   elf[name]={'ELF_class':bits,'e_machine':machine,'sha256':sha(p)}
  name='system/framework/wifi-service.rocsource.jar';p=target/name
  runtime_files[name]={'bytes':p.stat().st_size,'sha256':sha(p)}
 except (AssertionError,OSError) as error:
  artifact_error=str(error)

report={'phase':phase,'exit_status':status,'passed':status==0 and artifact_error is None,'prepare_receipt':latest,
 'product':'roc_os_release_candidate-user','candidate_sources_unchanged':True,
 'source64_protected_inputs_and_product_unchanged':True,'source64_three_images_unchanged':True,
 'artifact_validation_error':artifact_error,'runtime_files':runtime_files,
 'graph_sha256':graphs,'images':images,'actual_ELF':elf,'android_images_compiled':phase=='images' and status==0,'runtime_or_flash_accepted':False,'release_allowed':False}
receipt=next(OUT/('%s-result-v%d.json'%(phase,i)) for i in range(1,100) if not (OUT/('%s-result-v%d.json'%(phase,i))).exists())
receipt.write_text(json.dumps(report,indent=2)+'\n')
print('USER_CANDIDATE_'+phase.upper(), 'PASS' if report['passed'] else 'FAIL', 'ORIGINAL_ENGINEERING_IMAGES_UNCHANGED')

if artifact_error:
 print('USER_CANDIDATE_ARTIFACT_ERROR:',artifact_error)
 raise SystemExit(34)
