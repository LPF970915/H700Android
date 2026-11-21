"""Build and verify the five-panel Test20 card directly from the official Test14 test artifact."""

import argparse
import gzip
import json
from pathlib import Path
import shutil
import struct
import zlib

from package_h700_test14_rg34xx_menu import PARENT, PARENT_SHA, TEST14_IMAGE
from package_h700_shared_menu_test16 import (
    BOOT_OFFSET, CHUNK, ENV_OFFSET, ENV_SIZE, MODEL_PROFILE, PREFIX_BYTES, REPO, TOC_BYTES,
    TOC_OFFSET, VALUES, bridge, constrained, decode_env, digest, json_write, parts, patch_boot,
    read_toc, regular, require, sha, stream_ranges, verify_final_handoff, verify_gpt,
)
from package_h700_usb_device_test14 import boot_proof
from patch_ramdisk import parse
from five_panel_menu import GROUPS, REPS, build
from fit_bootlogo import fit_bootlogo
from test_five_panel_menu import hook_tests, picker_tests, state_tests

IMAGE = 'ROC_OS_ARM64_ver0.0.3_H700_Test20_FivePanel_Test14.img.gz'
MATRIX = tuple(row[:-1]+(0,) if i == 2 else row for i,row in enumerate(VALUES))


def early_patch(prefix):
    toc = bytearray(prefix[TOC_OFFSET:TOC_OFFSET + TOC_BYTES])
    entries = {e['name']: e for e in read_toc(toc)['items']}
    entry = entries['u-boot']
    start = entry['offset']
    old = bytes(toc[start:start + entry['bytes']])
    require(digest(old) == '226a0e1e972538b408e584346d5e1d108ecb65aea8c45bbf1bdc70f1c067f0cd',
            'Unexpected Test14 U-Boot')
    table = struct.pack('<13I', *VALUES[2])
    cave = old[bridge.START:bridge.LIMIT]
    require(cave.count(table) == 1, 'Ambiguous RG34XX LCD row')
    pos = bridge.START + cave.index(table)
    new = old[:pos] + struct.pack('<13I', *MATRIX[2]) + old[pos+len(table):]
    require(sum(a!=b for a,b in zip(old,new)) == 1, 'Unexpected early program change')
    toc[start:start+len(old)] = new
    struct.pack_into('<I', toc, 20, 0x5f0a6c39)
    struct.pack_into('<I', toc, 20, sum(x for x, in struct.iter_unpack('<I', toc)) & 0xffffffff)
    require(read_toc(toc)['bytes'] == TOC_BYTES, 'TOC checksum')
    env = prefix[ENV_OFFSET:ENV_OFFSET+ENV_SIZE]
    values = dict(decode_env(env))
    require(not {'roc_saved_model','roc_next_model','roc_next_start'} & values.keys(), 'Fresh menu expected')
    key = 'roc_2_lcd_frm'
    cmd = "fdt set /soc@03000000/lcd0@01c0c000 lcd_frm '<0x1>'"
    row = (key+'='+cmd).encode() + b'\0'
    require(values[key] == cmd and env.count(row) == 1, 'Wrong FRM setting')
    body = env[4:].replace(row, row.replace(b'0x1', b'0x0'))
    encoded = struct.pack('<I', zlib.crc32(body)) + body
    require(dict(decode_env(encoded)) == dict(values, **{key:cmd.replace('0x1','0x0')}), 'Unexpected env change')
    prefix[TOC_OFFSET:TOC_OFFSET+TOC_BYTES] = toc
    prefix[ENV_OFFSET:ENV_OFFSET+ENV_SIZE] = encoded
    dt = entries['dtb']
    return new, bytes(toc[dt['offset']:dt['offset']+dt['bytes']])


def early_tests(uboot, dtb):
    receipt = json.loads((REPO/'docs/baselines/roc-os-h700-twelve-model-test8-20261116/early-receipt.json').read_bytes())
    syms = {k:int(v,16) for k,v in receipt['symbols'].items()}
    old = regular(bridge.ORIGINAL).read_bytes()
    rows = []
    def run(env, model, route, held=False):
        result = bridge.execute(old, uboot, syms, env=env, samples=((0,) if held else (1,))*5,
                                slide=slide, fdt_blob=dtb)
        require(result['sets'] == dict(roc_active_model=model,roc_boot_route=route) and
                result['profile_values'] == list(MATRIX[MODEL_PROFILE[model]]) and result['r0'] == 0 and
                result['calls'].count('display_after_profile') == 1, 'Early LCD route ' + model)
        rows.append(dict(slide=slide, env=env, held=held, model=model, route=route, cells=result['profile_values']))
    for slide in (0,0x1000000):
        run({}, 'rg35xxh', 'selector')
        run({}, 'rg35xxh', 'selector', True)
        for model in REPS:
            run(dict(roc_saved_model='rgsp',roc_next_model=model,roc_next_start='2'),model,'selector')
        for model in MODEL_PROFILE:
            run(dict(roc_saved_model=model),model,'start_saved')
            run(dict(roc_saved_model=model),model,'selector',True)
            run(dict(roc_next_model=model,roc_next_start='1'),model,'start_once')
    return rows


def verify_ramdisk(original, updated, replacements):
    old_parts, new_parts = parts(original), parts(updated)
    for part in ('kernel','second','dtb'):
        require(old_parts[part]['data'] == new_parts[part]['data'], 'Unexpected changed component ' + part)
    def nodes(items):
        return parse(gzip.decompress(items['ramdisk']['data']))
    before, after = nodes(old_parts), nodes(new_parts)
    require(len(before) == len(after), 'CPIO count')
    for a,b in zip(before, after):
        require(dict(a,data=replacements.get(a['name'],a['data'])) == b, 'CPIO delta ' + a['name'])
    require(set(replacements) <= {n['name'] for n in after}, 'Missing menu component')


def package(work, output):
    constrained()
    parent = json.loads((PARENT/'verify-result.json').read_bytes())
    source = regular(PARENT/TEST14_IMAGE)
    require(parent['passed'] and sha(source) == parent['image_sha256'] == PARENT_SHA, 'Test14 parent identity')
    require(not work.exists() and not output.exists(), 'Use fresh work/output directories')
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    with gzip.open(source,'rb') as reader:
        prefix = bytearray(reader.read(PREFIX_BYTES))
        require(digest(prefix) == parent['raw']['ranges']['prefix'], 'Unexpected parent prefix')
        uboot, dtb = early_patch(prefix)
        res = next(row for row in parent['gpt'] if row['name']=='boot-resource')
        start, stop = res['offset'], res['offset']+res['bytes']
        volume, logo = fit_bootlogo(prefix[start:stop])
        prefix[start:stop] = volume
        require(all(logo['size'][0]<=row[1] and logo['size'][1]<=row[2] for row in MATRIX), 'Splash geometry')
        del volume
        replacements = build(work)
        boot = bytes(prefix[BOOT_OFFSET:])
        changed, delta = patch_boot(boot, replacements)
        verify_ramdisk(boot, changed, replacements)
        prefix[BOOT_OFFSET:] = changed
        del changed, boot
        print('Test14 verified. Testing the compiled group picker.', flush=True)
        tests = picker_tests(work,work/'selector')
        print('ARM64 group navigation passed. Testing state writes and hook rejections.', flush=True)
        tests['state'] = state_tests(work, work/'state', bytes(prefix[ENV_OFFSET:ENV_OFFSET+16*1024**2]))
        tests['hook'] = hook_tests(work)
        json_write(output/'menu-tests.json', tests)
        early = early_tests(uboot,dtb)
        json_write(output/'early-routes.json', early)
        prefix_path = work/'candidate-prefix.raw'
        prefix_path.write_bytes(prefix)
        prefix_hash = digest(prefix)
        old_values = verify_final_handoff.VALUES
        try:
            verify_final_handoff.VALUES = MATRIX
            handoffs = boot_proof(prefix_path, prefix_hash, output/'handoff')
        finally:
            verify_final_handoff.VALUES = old_values
        print(f'{len(early)} early display scenarios and {handoffs} kernel handoffs passed. Writing the full image.',flush=True)
        partial = output/(IMAGE+'.partial')
        with partial.open('xb') as f, gzip.GzipFile(filename='',fileobj=f,mode='wb',compresslevel=1,mtime=0) as writer:
            writer.write(prefix)
            shutil.copyfileobj(reader,writer,CHUNK)
    del prefix
    print('Reading back every byte of the compressed card and checking both GPTs.',flush=True)
    with gzip.open(partial,'rb') as reader:
        raw = stream_ranges(reader)
    gpt = verify_gpt(raw.pop('head'),raw.pop('tail'))
    require(gpt == parent['gpt'] and raw['ranges'] == dict(parent['raw']['ranges'],prefix=prefix_hash)
            and raw['bytes'] == parent['raw']['bytes'], 'Full card readback mismatch')
    checksum = sha(partial)
    image = output/IMAGE
    partial.rename(image)
    (output/(IMAGE+'.sha256')).write_text(f'{checksum}  {IMAGE}\n')
    json_write(output/'verify-result.json',dict(passed=True,image=IMAGE,image_sha256=checksum,
               bytes=image.stat().st_size,parent=TEST14_IMAGE,parent_sha256=PARENT_SHA,raw=raw,gpt=gpt,
               groups=GROUPS,volume_down=REPS,bootlogo=logo,rg34xx_frm=0,early_cases=len(early),
               kernel_handoffs=handoffs,menu_cases=len(tests['cases']),hook_cases=len(tests['hook']),
               changed_ramdisk_payloads=delta,physical_test20_verified=False,
               tests_sha256=sha(output/'menu-tests.json'),handoff_sha256=sha(output/'handoff/result.json')))
    print(checksum,image,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.work,args.output)
