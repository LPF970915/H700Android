#!/usr/bin/env python3
"""Record only the successful public build's own fresh partition outputs."""
from pathlib import Path
import argparse
import json
from common import regular, sha, write_json


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--product', type=Path, required=True)
    args = ap.parse_args()
    prepared = json.loads(regular(args.source / '.roc-public/prepare.json').read_text())
    files = {name: sha(regular(args.product / name)) for name in ['system.img', 'vendor.img', 'ramdisk.img']}
    write_json(args.product / 'public-build.json', {'passed': True, 'product': 'roc_os_release_candidate-user',
               'source_manifest_sha256': prepared['source_manifest_sha256'], 'images': files})
