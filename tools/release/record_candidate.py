"""Record isolated user graph status and protected inputs, including failures."""
from pathlib import Path
import hashlib,json,sys
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'tools'))
from package_h700_v6a import constrained
constrained()
OUT=REPO/'out/source64-user-candidate-20261104'
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
report={'phase':'graph','exit_status':status,'passed':status==0,'prepare_receipt':latest,
 'product':'roc_os_release_candidate-user','candidate_sources_unchanged':True,
 'source64_protected_inputs_and_product_unchanged':True,'source64_three_images_unchanged':True,
 'graph_sha256':graphs,'android_images_compiled':False,'runtime_or_flash_accepted':False}
receipt=next(OUT/('graph-result-v%d.json'%i) for i in range(1,100) if not (OUT/('graph-result-v%d.json'%i)).exists())
receipt.write_text(json.dumps(report,indent=2)+'\n')
print('USER_CANDIDATE_GRAPH', 'PASS' if status==0 else 'FAIL', 'ORIGINAL_ENGINEERING_IMAGES_UNCHANGED')
