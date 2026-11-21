"""Retain exact Test15 display and Android bytes with Test14 USB device mode."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from package_h700_rg34xx_first_menu import CHUNK, IMAGE as TEST15_IMAGE, REPO, constrained
from package_h700_usb_device_test14 import boot_proof, patch_usb
from rg35xxh_display import PREFIX_BYTES, TOC_OFFSET
from verify_002 import json_write, require, sha, stream_ranges, verify_gpt

PARENT = REPO / 'out/roc-os-h700-rg34xx-first-menu-test15-20261121'
PARENT_HASH = 'fe99e6c6fa9fa6334e656f8c0d66b1034102f4ca5ebfb2d6d2c7eac8a766cbe7'
IMAGE = 'ROC_OS_ARM64_ver0.0.3_H700_Test15_RG34XX_USB_Diagnosis_20261121.img.gz'


def package(output):
    constrained()
    parent_image = PARENT / TEST15_IMAGE
    require(sha(parent_image) == PARENT_HASH, 'Exact Test15 gzip required')
    parent = json.loads((PARENT / 'verify-result.json').read_text())
    require(parent['passed'] and parent['image_sha256'] == PARENT_HASH, 'Test15 receipt mismatch')
    output.mkdir(parents=True)
    final = output / IMAGE
    partial = final.with_suffix('.gz.partial')
    with gzip.open(parent_image, 'rb') as source:
        prefix = source.read(PREFIX_BYTES)
        require(hashlib.sha256(prefix).hexdigest() == parent['raw']['ranges']['prefix'],
                'Exact Test15 prefix required')
        updated, usb_offset = patch_usb(prefix)
        checksum_offset = TOC_OFFSET + 20
        require(usb_offset > checksum_offset + 4 and
                updated[:checksum_offset] == prefix[:checksum_offset] and
                updated[checksum_offset + 4:usb_offset] == prefix[checksum_offset + 4:usb_offset] and
                updated[usb_offset + 4:] == prefix[usb_offset + 4:], 'Unexpected boot prefix change')
        new_prefix_hash = hashlib.sha256(updated).hexdigest()
        proof_prefix = output / 'handoff-prefix.raw'
        proof_prefix.write_bytes(updated)
        cases = boot_proof(proof_prefix, new_prefix_hash, output / 'handoff')
        proof_prefix.unlink()
        print('USB device mode retained in the final handoff. Packaging exact Test15 data.', flush=True)
        with partial.open('xb') as artifact:
            with gzip.GzipFile(fileobj=artifact, filename='', mode='wb', compresslevel=1, mtime=0) as writer:
                writer.write(updated)
                while block := source.read(CHUNK):
                    writer.write(block)
    print('Reading back the complete diagnostic gzip.', flush=True)
    with gzip.open(partial, 'rb') as reader:
        raw = stream_ranges(reader)
    require(raw['ranges'] == dict(parent['raw']['ranges'], prefix=new_prefix_hash),
            'A partition outside the USB-only prefix changed')
    gpt = verify_gpt(raw.pop('head'), raw.pop('tail'))
    partial.rename(final)
    digest = sha(final)
    (output / (IMAGE + '.sha256')).write_text(f'{digest}  {IMAGE}\n', encoding='ascii')
    json_write(output / 'verify-result.json', {
        'passed': True, 'physical_usb_verified': False, 'display_runtime_changed': False,
        'image': IMAGE, 'image_bytes': final.stat().st_size, 'image_sha256': digest,
        'parent_image_sha256': PARENT_HASH, 'raw': raw, 'gpt': gpt,
        'changed_boot_windows': [[checksum_offset, 4], [usb_offset, 4]],
        'handoff_cases': cases, 'handoff_proof_sha256': sha(output / 'handoff/result.json'),
    })
    print(digest, final, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    package(parser.parse_args().output)
