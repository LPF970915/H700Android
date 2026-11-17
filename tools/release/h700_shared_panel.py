"""Assemble shared panel support in an exact0.0.2 ordinary prefix buffer.

No disk/device I/O. Default profile0 preserves all legacy numeric timings.
The same U-Boot/kernel pair contains both legacy720 and explicit35H programs.
"""
from pathlib import Path
import hashlib
import json
import struct

from rg35xxh_display import (PREFIX_BYTES, TOC_OFFSET, TOC_BYTES, BOOT_OFFSET,
    BOOT_BYTES, BASE_BOOT_SHA, BASE_TOC_SHA, boot_dtb_location, read_toc)
from h700_panel_profiles import add_carrier, validate_pair, select_profile

BASE_PREFIX_SHA='dddb456725f6ae0b0e3977c50747a23a8c91b66c55140959b9a58ab4f7ff425a'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(data):return hashlib.sha256(data).hexdigest()


def apply_driver(original,arch,artifact):
    require(len(original)==artifact['original_bytes'] and sha(original)==artifact['original_sha256'],
            'Driver parent mismatch: '+arch)
    bounds={'uboot':{'.dispatch':(0x26424,0x26afc),'.bridge_old':(0x26b18,0x26b1c),
                     '.frozen_tables':(0x26b28,0x2782e)},
            'kernel':{'.bridge_boe':(0x3a2b50,0x3a2b54),'.profile_dispatch':(0x3a2b60,0x3a3460),
                      '.bridge_old':(0x3a3460,0x3a3464),'.frozen_tables':(0x3a3480,0x3a41d4)}}[arch]
    require(len(artifact['sections'])==len(bounds),'Driver section count')
    require({row['name'] for row in artifact['sections']}==set(bounds),'Driver section set')
    output=bytearray(original);spans=[]
    for row in artifact['sections']:
        path=Path(row['file'])
        require(path.is_file() and not path.is_symlink(),'Ordinary driver section required')
        data=path.read_bytes()
        start,limit=bounds[row['name']]
        require(row['offset']==start and 0<len(data)<=limit-start and len(data)==row['bytes'], 'Driver section bounds')
        require(sha(data)==row['sha256'] and sha(original[start:start+len(data)])==row['before_sha256'],
                'Driver section source/output hash')
        output[start:start+len(data)]=data
        spans.append({'offset':start,'bytes':len(data),'component':arch,'role':row['name']})
    require(sha(output)==artifact['patched_sha256'],'Final driver hash mismatch')
    return bytes(output),spans


def toc_checksum(prefix):
    output=bytearray(prefix)
    struct.pack_into('<I',output,TOC_OFFSET+20,0x5f0a6c39)
    value=sum(struct.unpack_from('<'+str(TOC_BYTES//4)+'I',output,TOC_OFFSET))&0xffffffff
    struct.pack_into('<I',output,TOC_OFFSET+20,value)
    read_toc(output[TOC_OFFSET:TOC_OFFSET+TOC_BYTES])
    return bytes(output)


def patch_prefix(prefix,artifacts_path):
    require(len(prefix)==PREFIX_BYTES and sha(prefix)==BASE_PREFIX_SHA,'Exact0.0.2 prefix required')
    path=Path(artifacts_path)
    require(path.is_file() and not path.is_symlink(),'Ordinary artifact receipt')
    artifact_raw=path.read_bytes();artifacts=json.loads(artifact_raw)
    require(artifacts['passed'] is True,'Driver dispatch tests not complete')
    require(set(artifacts['architectures'])=={'uboot','kernel'},'Both architectures required')
    boot=prefix[BOOT_OFFSET:BOOT_OFFSET+BOOT_BYTES]
    require(sha(boot)==BASE_BOOT_SHA,'Parent boot changed')
    toc=prefix[TOC_OFFSET:TOC_OFFSET+TOC_BYTES]
    require(sha(toc)==BASE_TOC_SHA,'Parent TOC changed')
    meta=read_toc(toc);items={row['name']:row for row in meta['items']}
    require(set(items)=={'u-boot','monitor','dtbo','dtb'},'Unexpected TOC items')
    output=bytearray(prefix);spans=[]
    u=items['u-boot'];u_start=TOC_OFFSET+u['offset']
    require(u['offset']==2048 and u['bytes']==1048576,'Unexpected U-Boot placement')
    kernel_size,=struct.unpack_from('<I',boot,8)
    require(kernel_size==17686536 and struct.unpack_from('<I',boot,36)[0]==2048,'Kernel placement')
    k_start=BOOT_OFFSET+2048
    for arch,start,size in [('uboot',u_start,u['bytes']),('kernel',k_start,kernel_size)]:
        changed,delta=apply_driver(prefix[start:start+size],arch,artifacts['architectures'][arch])
        output[start:start+size]=changed
        spans += [dict(row,offset=start+row['offset']) for row in delta]
    d=items['dtb'];early_start=TOC_OFFSET+d['offset']
    require(d['offset']==1161216 and d['bytes']==143872,'Unexpected early FDT item')
    early,early_report=add_carrier(prefix[early_start:early_start+d['bytes']],keep_total=True)
    k_offset,k_total=boot_dtb_location(boot)
    require(k_offset==22081536 and k_total==137564,'Unexpected kernel FDT placement')
    kernel_start=BOOT_OFFSET+k_offset
    capacity=(k_total+2047)&~2047
    kernel,kernel_report=add_carrier(prefix[kernel_start:kernel_start+capacity],keep_total=False)
    require(validate_pair(early,kernel)==0,'Shared candidate must default720')
    output[early_start:early_start+len(early)]=early
    output[kernel_start:kernel_start+len(kernel)]=kernel
    struct.pack_into('<I',output,BOOT_OFFSET+1648,kernel_report['new_total'])
    spans += [{'offset':early_start,'bytes':len(early),'component':'uboot_fdt'},
              {'offset':kernel_start,'bytes':len(kernel),'component':'kernel_fdt'},
              {'offset':BOOT_OFFSET+1648,'bytes':4,'component':'boot_dtb_size'},
              {'offset':TOC_OFFSET+20,'bytes':4,'component':'toc_checksum'}]
    output=toc_checksum(output)
    cursor=0
    for row in sorted(spans,key=lambda x:x['offset']):
        require(row['offset']>=cursor,'Assembly windows overlap')
        require(output[cursor:row['offset']]==prefix[cursor:row['offset']],'Unexpected prefix delta')
        cursor=row['offset']+row['bytes']
    require(output[cursor:]==prefix[cursor:],'Unexpected prefix suffix')
    # Offline configuration must be reversible before any image packaging.
    selected,selection=configure_prefix(output,1)
    restored,_=configure_prefix(selected,0)
    require(restored==output,'Explicit profile roundtrip not byte-exact')
    return output,{'profile':0,'default':'retained720','available_profiles':[0,1],
        'automatic_hardware_identity':False,'first_selection':'explicit host configuration when ambiguous',
        'early_fdt':early_report,'kernel_fdt':kernel_report,'selected35H_fixture':selection,
        'driver_artifacts_sha256':sha(artifact_raw),'allowed_changed_spans':sorted(spans,key=lambda x:x['offset']),
        'boot_sha256':sha(output[BOOT_OFFSET:BOOT_OFFSET+BOOT_BYTES]),
        'toc_sha256':sha(output[TOC_OFFSET:TOC_OFFSET+TOC_BYTES]),
        'kernel_sha256':sha(output[k_start:k_start+kernel_size]),
        'runtime_display_accepted':False,'physical_card_written':False}


def configure_prefix(prefix,profile):
    """Change both complete panel configurations in a prepared prefix buffer."""
    require(len(prefix)==PREFIX_BYTES,'Shared prefix length')
    early_start,early_capacity=17954816,143872
    kernel_start,kernel_capacity=177270784,139264
    early=prefix[early_start:early_start+early_capacity]
    kernel=prefix[kernel_start:kernel_start+kernel_capacity]
    current=validate_pair(early,kernel)
    changed_early=select_profile(early,profile)
    changed_kernel=select_profile(kernel,profile)
    output=bytearray(prefix)
    output[early_start:early_start+early_capacity]=changed_early
    output[kernel_start:kernel_start+kernel_capacity]=changed_kernel
    output=toc_checksum(output)
    require(validate_pair(output[early_start:early_start+early_capacity],
                          output[kernel_start:kernel_start+kernel_capacity])==profile,'Profile pair readback')
    return output,{'before_profile':current,'after_profile':profile,'manual_configuration':True,
        'early_fdt_sha256':sha(changed_early),'kernel_fdt_sha256':sha(changed_kernel),
        'prefix_sha256':sha(output),'physical_card_written':False}
