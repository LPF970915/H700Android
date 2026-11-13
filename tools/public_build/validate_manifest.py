#!/usr/bin/env python3
"""Validate public repository inputs and copy recipes without an Android build."""
from collections import Counter
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import sys
from common import REPO, inside, regular, require_hash, sha, write_json


def relative_name(name):
    if not isinstance(name, str):
        raise ValueError('Manifest path must be a string')
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or name != path.as_posix()
            or '..' in path.parts or any(c in name for c in '\\\n\r\0')):
        raise ValueError(f'Unsafe manifest path: {name!r}')
    return name


def validate(manifest_path, repository=REPO):
    manifest_path = regular(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entries = manifest['files']
    by_path = {}
    kinds = Counter()
    repository_bytes = 0
    overlay_payloads = {}
    for entry in entries:
        name = relative_name(entry['path'])
        if name.endswith(('.pk8', '.temporary.pem')):
            raise ValueError(f'Private signing input is not public source: {name}')
        if name in by_path:
            raise ValueError(f'Duplicate output path: {name}')
        by_path[name] = entry
        if not isinstance(entry['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            raise ValueError(f'Invalid SHA256: {name}')
        if type(entry['bytes']) is not int or entry['bytes'] < 0:
            raise ValueError(f'Invalid byte count: {name}')
        if type(entry['mode']) is not int or not 0 <= entry['mode'] <= 0o777:
            raise ValueError(f'Invalid file mode: {name}')
        item = entry['input']
        kind = item['kind']
        if kind not in ('repository', 'source', 'image'):
            raise ValueError(f'Unknown input kind: {name}')
        kinds[kind] += 1
        if kind in ('repository', 'source'):
            relative_name(item['path'])
        if kind == 'repository':
            origin = require_hash(inside(repository, item['path']), entry['sha256'])
            if origin.stat().st_size != entry['bytes']:
                raise ValueError(f'Repository input byte count mismatch: {name}')
            repository_bytes += entry['bytes']
            if item['path'].startswith('build-support/public/overlay/'):
                overlay_payloads[item['path']] = entry['bytes']

    resolved = set()
    base_sources = set()
    copy_dependencies = 0

    def visit(name, visiting=()):
        nonlocal copy_dependencies
        if name in visiting:
            raise ValueError(f'Copy dependency cycle: {name}')
        if name in resolved:
            return
        entry = by_path[name]
        item = entry['input']
        if item['kind'] == 'source':
            dependency = by_path.get(item['path'])
            if dependency:
                if any(entry[key] != dependency[key] for key in ('sha256', 'bytes')):
                    raise ValueError(f'Copy depends on different source content: {name}')
                copy_dependencies += 1
                visit(item['path'], (*visiting, name))
            else:
                base_sources.add(item['path'])
        resolved.add(name)

    for name in by_path:
        visit(name)
    expected = {'files': len(entries), 'new_payload_bytes': sum(overlay_payloads.values()),
                'input_kinds': dict(kinds)}
    if manifest.get('statistics') != expected:
        raise ValueError(f'Manifest statistics mismatch; expected {expected}')
    relative_name(manifest['signing_link'])
    for name, digest in manifest['base_checks'].items():
        relative_name(name)
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError(f'Invalid base-check SHA256: {name}')
    records = [{key: entry[key] for key in ('path', 'bytes', 'mode', 'sha256')}
               for entry in sorted(entries, key=lambda value: value['path'])]
    identity = json.dumps(records, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {
        'passed': True,
        'scope': 'Repository payload hash/size closure and source-copy recipes only; '
                 'base source bodies and image payloads are not read by this check.',
        'source_manifest_sha256': sha(manifest_path),
        'target_identity_sha256': hashlib.sha256(identity).hexdigest(),
        'target_identity_algorithm': 'SHA256 of UTF-8 JSON, sort_keys=true, ensure_ascii=true, separators=comma/colon, '
                                     'no final newline; path-sorted records of path,bytes,mode,sha256.',
        **expected,
        'new_payload_bytes_definition': 'Unique repository input paths under build-support/public/overlay/',
        'repository_target_bytes_verified': repository_bytes,
        'source_copy_dependencies_verified': copy_dependencies,
        'unique_base_source_inputs_not_read': len(base_sources),
        'image_payloads_not_read': kinds['image'],
        'independent_clean_full_Android_build_passed': False,
        'hardware_acceptance_performed': False,
    }


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, default=REPO / 'build-support/public/source-manifest.json')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    try:
        result = validate(args.manifest)
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)
