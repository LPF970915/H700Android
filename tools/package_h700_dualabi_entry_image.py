#!/usr/bin/env python3
"""Compose immutable P1a full-image gzip from P1 ranges and verified entry fix."""
from pathlib import Path
import gzip
import hashlib
import json
import package_h700_v6a as base
from prepare_h700_dualabi_boot_entry import ROOT, PARENT, WORK, OUT

def main():
    base.constrained()
    entry=json.loads((OUT/'entry-lock.json').read_text())
    parent=json.loads((ROOT/'docs/baselines/rg34xxsp-dualabi-spare-p1-20261031/image-lock.json').read_text())
    ranges=[]
    for e in parent['ranges']:
        source=WORK/'system.candidate.raw' if e['name']=='system' else PARENT/(e['name']+'.candidate.raw')
        expected=entry['system_sha256'] if e['name']=='system' else e['sha256']
        base.regular(source)
        if source.stat().st_size!=e['bytes'] or base.sha(source)!=expected:raise ValueError('P1a source range mismatch')
        ranges.append({'name':e['name'],'offset':e['offset'],'bytes':e['bytes'],'sha256':expected,'source':source})
    release='H700_RG34XXSP_2GB_DualABI_P1a_GSI10_20261031_NoROM'
    target=OUT/(release+'.img.gz')
    if target.exists():raise ValueError('Preserve the existing P1a image')
    digest=hashlib.sha256()
    with target.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=6,mtime=0,filename='') as z:
        for e in ranges:
            print('P1A_COMPRESS',e['name'],flush=True)
            with e['source'].open('rb') as f:
                while b:=f.read(8*1024**2):digest.update(b);z.write(b)
    check=hashlib.sha256();total=0
    with gzip.open(target,'rb') as f:
        for e in ranges:
            remaining=e['bytes'];part=hashlib.sha256()
            while remaining:
                b=f.read(min(8*1024**2,remaining))
                if not b:raise ValueError('Short decompression')
                part.update(b);check.update(b);remaining-=len(b);total+=len(b)
            if part.hexdigest()!=e['sha256']:raise ValueError('P1a decompressed range mismatch')
        if f.read(1):raise ValueError('Unexpected gzip tail')
    if total!=parent['bytes'] or check.hexdigest()!=digest.hexdigest():raise ValueError('P1a full decompression mismatch')
    result={'release':release,'bytes':total,'sha256':digest.hexdigest(),'gzip_bytes':target.stat().st_size,
            'gzip_sha256':base.sha(target),'ranges':[{k:v for k,v in e.items() if k!='source'} for e in ranges],
            'layout':parent['layout'],'runtime_marker':parent['marker'],'entry_revision':entry['revision'],
            'full_gzip_decompression_verified':True,'all_decompressed_range_hashes_verified':True,
            'source_parent_checkpoint':'baseline/rg34xxsp-dualabi-spare-p1-20261031',
            'fresh_whole_card_flash':False,'fresh_first_boot':False,'rom_bios_accounts_saves':False}
    base.jsonwrite(OUT/'image-lock.json',result)
    print('P1A_FULL_IMAGE_GZIP_VERIFIED',flush=True)

if __name__=='__main__':main()
