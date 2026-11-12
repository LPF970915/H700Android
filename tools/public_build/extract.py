#!/usr/bin/env python3
"""Extract pinned boot assets and build inputs from an ordinary 0.0.1 image."""
from pathlib import Path
import argparse
import gzip
import hashlib
import sys
from common import REPO, inside, load, regular, require_hash, run, sparse_write, write_json
sys.path.insert(0, str(REPO / 'tools'))
from android_bootimg import read_header, component_offsets
from patch_ramdisk import parse


def verify_boot_sources(output, spec):
    boot = output / 'boot.raw'
    with (output / 'prefix.raw').open('rb') as stream:
        stream.seek(spec['boot']['offset'])
        body = stream.read(spec['boot']['bytes'])
    boot.write_bytes(body)
    _, header = read_header(boot)
    offsets = component_offsets(header)
    entries = {e['name']: e for e in parse(gzip.decompress(body[offsets['ramdisk']:offsets['ramdisk']+header['ramdisk_size']]))}
    for item in load('boot-sources.json')['files']:
        require_hash(inside(REPO, item['repository_path']), item['sha256'])
        if hashlib.sha256(entries[item['archive_name']]['data']).hexdigest() != item['sha256']:
            raise ValueError('Boot script differs from published source: ' + item['archive_name'])


def extract(image, output):
    spec = load('external-inputs.json')['reference_image']
    image = require_hash(image, spec['sha256'])
    if image.stat().st_size != spec['bytes']:
        raise ValueError('Wrong compressed image size')
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('Output must be a new directory; prior results are preserved')
    output.mkdir(parents=True)
    streams = {}
    digests = {}
    ranges = spec['ranges']
    for name, r in ranges.items():
        streams[name] = (output / (name + '.raw')).open('xb')
        digests[name] = hashlib.sha256()
    position = 0
    raw_hash = hashlib.sha256()
    try:
        with gzip.open(image, 'rb') as source:
            while block := source.read(1024 * 1024):
                if position + len(block) > spec['raw_bytes']:
                    raise ValueError('Image expands beyond the pinned size')
                raw_hash.update(block)
                for name, r in ranges.items():
                    start = max(position, r['offset'])
                    end = min(position + len(block), r['offset'] + r['bytes'])
                    if start < end:
                        piece = block[start-position:end-position]
                        sparse_write(streams[name], piece)
                        digests[name].update(piece)
                position += len(block)
        if position != spec['raw_bytes'] or raw_hash.hexdigest() != spec['raw_sha256']:
            raise ValueError('Decompressed image identity mismatch')
        for name, r in ranges.items():
            streams[name].truncate(r['bytes'])
            if digests[name].hexdigest() != r['sha256']:
                raise ValueError(f'Partition identity mismatch: {name}')
    finally:
        for stream in streams.values():
            stream.close()
    verify_boot_sources(output, spec)
    manifest = load('source-manifest.json')
    extracted = {}
    for entry in manifest['files']:
        origin = entry['input']
        if origin['kind'] != 'image':
            continue
        destination = inside(output / 'files', entry['path'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Paths are controlled by the published manifest; debugfs has its own parser.
        if any(c.isspace() for c in origin['path'] + str(destination)):
            raise ValueError('Use an input/output directory without spaces for debugfs')
        run(['debugfs', '-R', f"dump {origin['path']} {destination}", output / (origin['partition'] + '.raw')])
        require_hash(destination, entry['sha256'])
        destination.chmod(entry['mode'])
        extracted[entry['path']] = entry['sha256']
    # No userdata range is extracted, including the original workstation authorization.
    write_json(output / 'extraction.json', {'passed': True, 'image_sha256': spec['sha256'],
               'raw_sha256': raw_hash.hexdigest(), 'files': extracted,
               'userdata_extracted': False, 'physical_device_accessed': False})
    print(f'EXTRACTED {len(extracted)} files; no userdata or host authorization copied', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    try:
        extract(args.image, args.output)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)
