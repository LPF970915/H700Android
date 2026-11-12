#!/usr/bin/env python3
"""Verify downloaded archives without unpacking or contacting a device."""
from pathlib import Path
import argparse
import hashlib
from common import load, regular


def check(path, spec):
    path = regular(path)
    if path.stat().st_size != spec['bytes']:
        raise ValueError('Wrong file size: ' + str(path))
    digests = {key: hashlib.new(key) for key in ['sha256', 'md5'] if spec.get(key)}
    with path.open('rb') as stream:
        while block := stream.read(4 * 1024**2):
            for value in digests.values():
                value.update(block)
    for key, value in digests.items():
        if value.hexdigest() != spec[key]:
            raise ValueError(f'{key} mismatch: {path}')
    print('VERIFIED', path.name, flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--android', type=Path)
    ap.add_argument('--longan', type=Path)
    ap.add_argument('--image', type=Path)
    args = ap.parse_args()
    if not any([args.android, args.longan, args.image]):
        ap.error('Provide at least one downloaded input')
    spec = load('external-inputs.json')
    archives = {s['name']: s for s in spec['source_archives']}
    for path, item in [(args.android, archives['android.tar.gz']),
                       (args.longan, archives['longan.tar.gz']),
                       (args.image, spec['reference_image'])]:
        if path:
            check(path, item)
