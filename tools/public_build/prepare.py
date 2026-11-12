#!/usr/bin/env python3
"""Apply the final source overlay to a separately unpacked Android BSP tree."""
from pathlib import Path, PurePosixPath
import argparse
import json
import os
import shutil
import sys
from common import REPO, inside, load, regular, require_hash, run, sha, write_json

ROLES = ('releasekey', 'platform', 'shared', 'media', 'networkstack')


def prepare(source, inputs, keys, apply=False):
    source = Path(source).resolve()
    inputs = Path(inputs).resolve()
    keys = Path(keys).resolve()
    regular(source / 'build/envsetup.sh')
    if keys.is_relative_to(source) or keys.is_relative_to(REPO):
        raise ValueError('Keep private signing keys outside source and repository')
    for role in ROLES:
        regular(keys / (role + '.pk8'))
        regular(keys / (role + '.x509.pem'))
        key = run(['openssl', 'pkey', '-inform', 'DER', '-in', keys / (role + '.pk8'), '-pubout']).stdout
        cert = run(['openssl', 'x509', '-in', keys / (role + '.x509.pem'), '-pubkey', '-noout']).stdout
        if key != cert:
            raise ValueError(f'Certificate/key mismatch: {role}')
    manifest = load('source-manifest.json')
    extraction = json.loads(regular(inputs / 'extraction.json').read_text())
    if not extraction['passed'] or extraction['image_sha256'] != load('external-inputs.json')['reference_image']['sha256']:
        raise ValueError('Verified reference-image extraction is required')
    for name, digest in manifest['base_checks'].items():
        require_hash(inside(source, name), digest)
    by_path = {e['path']: e for e in manifest['files']}
    if len(by_path) != len(manifest['files']):
        raise ValueError('Duplicate output path')

    def origin(entry, visiting=()):
        if entry['path'] in visiting:
            raise ValueError('Copy dependency cycle')
        item = entry['input']
        if item['kind'] == 'repository':
            path = inside(REPO, item['path'])
        elif item['kind'] == 'image':
            path = inside(inputs / 'files', entry['path'])
        elif item['kind'] == 'source':
            dependency = by_path.get(item['path'])
            if dependency:
                if dependency['sha256'] != entry['sha256']:
                    raise ValueError('Copy depends on different source content')
                return origin(dependency, (*visiting, entry['path']))
            path = inside(source, item['path'])
        else:
            raise ValueError('Unknown input kind')
        return require_hash(path, entry['sha256'])

    plan = []
    for entry in manifest['files']:
        src = origin(entry)
        dest = inside(source, entry['path'])
        if dest.is_symlink():
            raise ValueError(f'Refuse replacing a source symlink: {entry["path"]}')
        plan.append((entry, src, dest))
    signing_name = PurePosixPath(manifest['signing_link'])
    link = inside(source, signing_name.parent.as_posix()) / signing_name.name
    if link.is_symlink() and link.resolve() != keys:
        raise ValueError('Existing signing link uses another identity')
    if link.exists() and not link.is_symlink():
        raise ValueError('Signing link location is occupied')
    marker = source / '.roc-public/prepare.json'
    if marker.exists():
        raise ValueError('This tree was already prepared; use its existing build output for incremental builds')
    print(f'VALIDATED {len(plan)} source files and five matching signing roles', flush=True)
    if not apply:
        print('PLAN ONLY; use --apply to stage this tree', flush=True)
        return
    backup = source / '.roc-public/before'
    for entry, src, dest in plan:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and sha(dest) != entry['sha256']:
            saved = inside(backup, entry['path'])
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, saved)
        if not dest.exists() or sha(dest) != entry['sha256']:
            temporary = dest.with_name(dest.name + '.roc-new')
            with temporary.open('xb') as stream, src.open('rb') as original:
                shutil.copyfileobj(original, stream)
            temporary.chmod(entry['mode'])
            os.replace(temporary, dest)
        dest.chmod(entry['mode'])
        require_hash(dest, entry['sha256'])
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.is_symlink():
        link.symlink_to(keys, target_is_directory=True)
    write_json(marker, {'passed': True, 'source_manifest_sha256': sha(REPO / 'build-support/public/source-manifest.json'),
               'files': len(plan), 'private_keys_copied': False, 'image_userdata_copied': False,
               'full_rebuild_performed': False, 'product': manifest['source_target']})
    print('PREPARED; keys remain external; no build or device operation performed', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--keys', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    try:
        prepare(args.source, args.inputs, args.keys, args.apply)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(2)
