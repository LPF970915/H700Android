"""Record actual build exit status and check that protected sources stayed unchanged."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained
constrained()
phase, status = sys.argv[1], int(sys.argv[2])
assert phase in {'graph', 'images'}
OUT = REPO / 'out/roc-os-source64-20261103'
latest = json.loads((OUT / 'latest-prepare.json').read_text())
prepared = json.loads((OUT / latest['receipt']).read_text())
native = Path(prepared['native_root'])
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert all(sha(native / name) == digest for name, digest in prepared['protected_native_sha256'].items())
product = native / 'device/roc/roc_os_source64'
assert all(sha(product / name) == digest for name, digest in prepared['product_sha256'].items())
images = {}
if phase == 'images' and status == 0:
    target = Path(prepared['out_dir']) / 'target/product/roc_os_source64'
    for name in ['system.img', 'vendor.img', 'ramdisk.img']:
        p = target / name
        assert p.is_file() and p.stat().st_size > 0, name
        images[name] = {'bytes': p.stat().st_size, 'sha256': sha(p)}
result = {'phase': phase, 'exit_status': status, 'passed': status == 0,
          'prepare_receipt': latest['receipt'], 'protected_sources_unchanged': True,
          'product_sources_unchanged_during_build': True, 'images': images,
          'full_source_image_build_passed': phase == 'images' and status == 0,
          'device_boot_accepted': False, 'current_card_modified': False}
p = next(OUT / ('%s-result-v%d.json' % (phase, n)) for n in range(1, 100)
         if not (OUT / ('%s-result-v%d.json' % (phase, n))).exists())
p.write_text(json.dumps(result, indent=2) + '\n')
print('SOURCE64_RESULT', phase, 'PASS' if status == 0 else 'FAIL', 'protected sources unchanged', flush=True)
