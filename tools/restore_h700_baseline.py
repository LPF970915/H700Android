#!/usr/bin/env python3
"""Verify/restore the frozen source overlay. Never builds, flashes or deletes inputs."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'docs/baselines/h700-v5i-usb-network-20261028/source-lock.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(root, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or not relative.parts or any(p in ('..', '') for p in relative.parts):
        raise ValueError('Unsafe relative path: ' + name)
    target = root.joinpath(*relative.parts)
    # Inspect before resolving, so symlinks cannot hide behind a valid prefix.
    for candidate in [root, *target.parents, target]:
        if candidate.is_symlink():
            raise ValueError('Symlink in restore path: ' + str(candidate))
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Restore path escapes root: ' + name)
    return target


def verify_snapshot(root=ROOT, lock=LOCK):
    manifest = json.loads(lock.read_text(encoding='utf-8'))
    entries = []
    for relative, record in manifest['files'].items():
        source = safe_path(root, record['repository_path'])
        if not source.is_file() or source.stat().st_size != record['bytes'] or digest(source) != record['sha256']:
            raise ValueError('Frozen source mismatch: ' + relative)
        entries.append((relative, source, record))
    if not entries:
        raise ValueError('Empty source overlay')
    return entries


def restore(source_root, backup=None, apply=False):
    source_root = source_root.absolute()
    if not (source_root / 'build/envsetup.sh').is_file():
        raise ValueError('Expected an unpacked H616 Android 10 source tree')
    entries = verify_snapshot()
    plan = []
    for relative, source, record in entries:
        target = safe_path(source_root, relative)
        if target.exists() and not target.is_file():
            raise ValueError('Non-file restore target: ' + relative)
        if target.is_file() and digest(target) == record['sha256']:
            continue
        plan.append((relative, source, target, record))
    result = {'mode': 'apply' if apply else 'plan', 'snapshot_files': len(entries),
              'changed_files': len(plan), 'paths': [p[0] for p in plan],
              'device_access': False, 'build_started': False}
    if not apply or not plan:
        return result
    if backup is None:
        raise ValueError('--apply requires a new --backup directory')
    backup = backup.absolute()
    if backup.exists() or backup.is_relative_to(source_root) or backup.is_symlink():
        raise ValueError('Backup must be new and outside the source tree')
    for parent in backup.parents:
        if parent.is_symlink():
            raise ValueError('Symlink in backup path')
    backup.mkdir(parents=True)
    journal = []
    # Back up ALL originals before the first source mutation.
    for relative, _, target, _ in plan:
        item = {'path': relative, 'existed': target.exists()}
        if target.exists():
            saved = safe_path(backup, relative)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            item['before_sha256'] = digest(saved)
            if item['before_sha256'] != digest(target):
                raise ValueError('Backup readback mismatch: ' + relative)
        journal.append(item)
    (backup / 'restore-journal.json').write_text(json.dumps(journal, indent=2) + '\n')
    for relative, source, target, record in plan:
        safe_path(source_root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else record['mode']
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.h700-restore-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source.read_bytes())
        temporary.chmod(mode)
        temporary.replace(target)
        if digest(target) != record['sha256']:
            raise ValueError('Restored source mismatch: ' + relative)
    result['backup'] = str(backup)
    (backup / 'restore-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.source:
        result = restore(args.source, args.backup, args.apply)
    else:
        if args.apply or args.backup:
            parser.error('--apply/--backup require --source')
        entries = verify_snapshot()
        result = {'mode': 'verify', 'snapshot_files': len(entries),
                  'snapshot_bytes': sum(e[2]['bytes'] for e in entries),
                  'device_access': False, 'build_started': False}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
