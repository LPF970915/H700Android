#!/usr/bin/env python3
"""Record only the successful public build's own fresh partition outputs."""
from pathlib import Path
import argparse
import json
import stat
from common import REPO, inside, regular, require_hash, require_manifest_binding, sha, write_json


def prepared_receipt(source):
    prepared = json.loads(regular(Path(source) / '.roc-public/prepare.json').read_text())
    require_manifest_binding(prepared)
    manifest = json.loads(regular(REPO / 'build-support/public/source-manifest.json').read_text())
    for entry in manifest['files']:
        target = require_hash(inside(source, entry['path']), entry['sha256'])
        if target.stat().st_size != entry['bytes']:
            raise ValueError(f'Prepared source byte count mismatch: {entry["path"]}')
        if stat.S_IMODE(target.stat().st_mode) != entry['mode']:
            raise ValueError(f'Prepared source mode mismatch: {entry["path"]}')
    return prepared


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--product', type=Path)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    prepared = prepared_receipt(args.source)
    if args.check_only:
        print('PREPARED_MANIFEST_AND_LISTED_SOURCE_FILES_MATCH_CURRENT_SOURCE')
        raise SystemExit(0)
    if args.product is None:
        ap.error('--product is required unless --check-only is used')
    files = {name: sha(regular(args.product / name)) for name in ['system.img', 'vendor.img', 'ramdisk.img']}
    write_json(args.product / 'public-build.json', {'passed': True, 'product': 'roc_os_release_candidate-user',
               'source_manifest_sha256': prepared['source_manifest_sha256'], 'images': files})
