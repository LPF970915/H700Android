"""Promote the exact five-panel Test20 card to ROC OS 0.0.4 (ordinary files only)."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_003 import CHUNK, PROPS, RANGES, RAW_BYTES, SYSTEM_BYTES, SYSTEM_OFFSET, fs, require, sha
from verify_002 import constrained, regular, stream_ranges, verify_gpt

BASE = '60872656ddc9f0f71ec026d965f7c2a3e17f5eaebc484e7c6867da86f970b87d'
RAW = '8f4041e00d4b3ba58b39710a95e455a6e8510656cd3ea5fdd201f40e0af09e76'
NAME = 'ROC_OS_ARM64_ver0.0.4.img.gz'


def package(parent, work, out):
    constrained()
    receipt = json.loads((parent.parent / 'verify-result.json').read_bytes())
    require(receipt['passed'] and receipt['image_sha256'] == BASE == sha(regular(parent))
            and receipt['raw']['sha256'] == RAW, 'Expected verified Test20')
    require(not work.exists() and not out.exists(), 'Fresh work and output paths required')
    work.mkdir(parents=True)
    out.mkdir(parents=True)
    system = work / 'system.ext4'
    print('Inspecting Test20 system version and ext4 blocks', flush=True)
    with gzip.open(parent, 'rb') as stream, system.open('xb') as f:
        stream.seek(SYSTEM_OFFSET)
        remaining = SYSTEM_BYTES
        while remaining:
            data = stream.read(min(CHUNK, remaining))
            require(bool(data), 'Incomplete system')
            if data.count(0) == len(data):
                f.seek(len(data), os.SEEK_CUR)
            else:
                f.write(data)
            remaining -= len(data)
        f.truncate(SYSTEM_BYTES)
    require(sha(system) == receipt['raw']['ranges']['system'], 'Parent system identity')
    original = fs(system, 'cat ' + PROPS)
    before_stat = fs(system, 'stat ' + PROPS)
    props = original
    positions = []
    fsinfo = subprocess.check_output(['/usr/sbin/dumpe2fs','-h',system], stderr=subprocess.DEVNULL)
    require(re.search(rb'^Block size:\s+4096$',fsinfo,re.M), 'Unexpected ext4 block size')
    with system.open('r+b') as partition:
        for key,value in [(b'ro.build.display.id',b'ROC_OS_ARM64_ver0.0.3'),(b'ro.roc.os.version',b'0.0.3')]:
            old = key + b'=' + value
            matches = list(re.finditer(b'^' + re.escape(old) + b'$', original, re.M))
            require(len(matches) == 1, 'Unexpected Test20 version properties')
            logical, index = divmod(matches[0].end() - 1, 4096)
            block = int(fs(system, f'bmap {PROPS} {logical}').strip())
            offset = block * 4096 + index
            require(0 < offset < SYSTEM_BYTES, 'Property outside filesystem')
            partition.seek(offset)
            require(partition.read(1) == b'3', 'Expected version digit')
            partition.seek(offset)
            partition.write(b'4')
            positions.append(SYSTEM_OFFSET + offset)
            props = props.replace(old, old[:-1]+b'4')
    require(fs(system,'cat '+PROPS) == props and fs(system,'stat '+PROPS) == before_stat, 'Version or inode readback')
    subprocess.run(['/usr/sbin/e2fsck','-f','-n',system],check=True)
    expected_ranges = dict(receipt['raw']['ranges'], system=sha(system))
    print('Writing release. Only the two version digits change.', flush=True)
    before, after = hashlib.sha256(), hashlib.sha256()
    partial = out / (NAME + '.partial')
    total = 0
    writes = 0
    with gzip.open(parent,'rb') as reader, partial.open('xb') as disk, gzip.GzipFile(
            filename='',fileobj=disk,mode='wb',mtime=0,compresslevel=1) as writer:
        while data := reader.read(CHUNK):
            before.update(data)
            for pos in positions:
                if total <= pos < total+len(data):
                    idx = pos-total
                    require(data[idx:idx+1] == b'3','Unexpected original digit')
                    data = data[:idx]+b'4'+data[idx+1:]
                    writes += 1
            after.update(data)
            writer.write(data)
            total += len(data)
    require(total == RAW_BYTES and writes == 2 and before.hexdigest() == RAW, 'Whole parent identity')
    print('Reading back the release and verifying complete raw bytes and GPT', flush=True)
    with gzip.open(partial,'rb') as reader:
        actual = stream_ranges(reader)
    gpt = verify_gpt(actual.pop('head'),actual.pop('tail'))
    require(gpt == receipt['gpt'] and actual['ranges'] == expected_ranges
            and actual['sha256'] == after.hexdigest(), 'Whole image readback')
    checksum = sha(partial)
    partial.rename(out / NAME)
    (out / (NAME+'.sha256')).write_text(f'{checksum}  {NAME}\n')
    result = dict(version='0.0.4',passed=True,artifact=NAME,bytes=(out/NAME).stat().st_size,
                  sha256=checksum,raw_bytes=total,raw_sha256=actual['sha256'],base_gzip_sha256=BASE,
                  base_raw_sha256=RAW,changed_byte_offsets=positions,changed_properties=['ro.build.display.id',
                  'ro.roc.os.version'],ranges=actual['ranges'],gpt=gpt,system_fsck_passed=True,
                  unchanged_build_prop_inode=True,full_gzip_readback=True)
    (out/'verify-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(checksum, NAME, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','work','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args = p.parse_args()
    package(args.parent,args.work,args.output)
