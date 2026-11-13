"""Shared offline helpers for the public H700 build path."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import stat
import subprocess

REPO = Path(__file__).resolve().parents[2]
SUPPORT = REPO / 'build-support/public'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path):
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.is_symlink():
        raise ValueError(f'Require an ordinary file, not a device or link: {path}')
    return path


def inside(root, name):
    p = PurePosixPath(name)
    if p.is_absolute() or not p.parts or '..' in p.parts or any(c in name for c in '\\\n\r\0'):
        raise ValueError(f'Unsafe relative path: {name!r}')
    root = Path(root).resolve()
    target = root.joinpath(*p.parts)
    if not target.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes root: {name}')
    return target


def load(name):
    return json.loads((SUPPORT / name).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(args, allowed=(0,), **kwargs):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True, **kwargs)
    if p.returncode not in allowed:
        raise RuntimeError(f'{args[0]} exited {p.returncode}:\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}')
    return p


def sparse_write(stream, block):
    if block.count(0) == len(block):
        stream.seek(len(block), os.SEEK_CUR)
    else:
        stream.write(block)


def copy_sparse(source, target, offset=0):
    with regular(source).open('rb') as stream:
        target.seek(offset)
        while block := stream.read(1024 * 1024):
            sparse_write(target, block)


def require_hash(path, expected):
    path = regular(path)
    if not expected or sha(path) != expected:
        raise ValueError(f'SHA256 mismatch: {path}')
    return path


def require_manifest_binding(receipt):
    expected = sha(regular(REPO / 'build-support/public/source-manifest.json'))
    if receipt.get('passed') is not True or receipt.get('source_manifest_sha256') != expected:
        raise ValueError('Receipt does not match the current public source manifest; '
                         'prepare a separate tree for this source revision')
    return expected
