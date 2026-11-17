"""Integrate a twelve-model selector into ordinary shared-panel boot bytes.

No device access. The caller supplies reviewed early-bridge and helper artifacts.
Electrical programs remain explicit, including distinct same-size panel timings.
"""
from pathlib import Path
import copy
import gzip
import hashlib
import json
import stat
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from patch_ramdisk import parse, emit
from h700_panel_boot import decode_env, ENV_OFFSET, ENV_SIZE
from h700_panel_profiles import TIMINGS, PANEL, KEY, validate_profile
from h700_shared_panel import toc_checksum
from rg35xxh_display import BOOT_OFFSET, BOOT_BYTES, PREFIX_BYTES, TOC_OFFSET, read_toc

BASE_INIT_SHA = '454c666b454bfcafc1afa96ba9b7665ce1f9b62a2e730b7f7009fde71f39273a'
MENU_SHA = '319d745b3853b1bf60d81a7e75370d3c01b2b5a544fd6ae17633fd473a19808b'
sys.path.insert(0, str(ROOT / 'tools/boot_selector/twelve_model'))
from models import ALL_MODEL_IDS, MODEL_METADATA, MODEL_PROFILE, TIMINGS
SUPPORTED = list(ALL_MODEL_IDS)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def align(n):
    return (n + 2047) & ~2047


def parts(boot):
    require(len(boot) == BOOT_BYTES and boot[:8] == b'ANDROID!', 'Unexpected boot container')
    require(struct.unpack_from('<I', boot, 36)[0] == 2048, 'Expected 2048 page')
    require(struct.unpack_from('<I', boot, 40)[0] == 2, 'Expected Android v2 header')
    require(struct.unpack_from('<I', boot, 1632)[0] == 0 and struct.unpack_from('<Q', boot, 1636)[0] == 0,
            'Unexpected recovery dtbo requires separate layout handling')
    require(struct.unpack_from('<I', boot, 1644)[0] == 1660, 'Unexpected header_size')
    sizes = {key: struct.unpack_from('<I', boot, offset)[0]
             for key, offset in [('kernel', 8), ('ramdisk', 16), ('second', 24), ('dtb', 1648)]}
    offset = 2048
    result = {}
    for name in ('kernel', 'ramdisk', 'second', 'dtb'):
        size = sizes[name]
        result[name] = {'offset': offset, 'bytes': size, 'data': boot[offset:offset + size]}
        require(len(result[name]['data']) == size, 'Truncated component')
        offset += align(size)
    result['end'] = offset
    require(struct.unpack_from('>II', result['dtb']['data'])[0] == 0xd00dfeed and
            struct.unpack_from('>I', result['dtb']['data'], 4)[0] == sizes['dtb'], 'v2 DTB header mismatch')
    return result


def kernel_commands(dtb_offset):
    address = 0x45000000 + dtb_offset
    require(0x45000000 < address < 0x49000000, 'Kernel FDT outside loaded boot window')
    # This U-Boot has the simple parser, not Hush. Each variable is exactly one
    # command; actual do_run stops at the first failed variable, including a
    # failed nested run. Never replace this with semicolon/&&/if control flow.
    commands = {
        # The literal substring is also checked by the unchanged boot-state v2.
        'boot_normal': 'run roc_selector_apply',
        'roc_selector_schema': '2',
        'roc_selector_apply': 'run roc_load_boot roc_dispatch roc_boot_args roc_boot_kernel',
        'roc_load_boot': 'sunxi_flash read 45000000 boot',
        'roc_dispatch': 'run roc_apply_${roc_active_model}',
        'roc_fdt_addr': 'fdt addr ${fdtcontroladdr}',
    }
    for profile, timings in TIMINGS.items():
        props = {'roc_panel_profile': profile, **timings}
        for name, value in props.items():
            commands[f'roc_{profile}_{name}'] = f"fdt set {PANEL} {name} '<0x{value:x}>'"
    for model in SUPPORTED:
        profile = MODEL_PROFILE[model]
        names = [f'roc_{profile}_{name}' for name in ('roc_panel_profile', *TIMINGS[profile])]
        lid = int(MODEL_METADATA[model]['lid'])
        commands['roc_apply_' + model] = 'run ' + ' '.join(['roc_fdt_addr'] + names + [f'roc_lid{lid}'])
        metadata = MODEL_METADATA[model]
        native_width, native_height = metadata['native_size']
        logical_width, logical_height = metadata['geometry'].split('x')
        commands['roc_boot_args_' + model] = (
            'setenv bootargs ${bootargs} androidboot.roc_model=' + model +
            ' androidboot.roc_clamshell=' + str(lid) +
            ' androidboot.roc_route=${roc_boot_route}' +
            ' androidboot.roc_sticks=' + str(metadata['sticks']) +
            ' androidboot.roc_form_factor=' + metadata['form_factor'] +
            ' androidboot.roc_native_width=' + str(native_width) +
            ' androidboot.roc_native_height=' + str(native_height) +
            ' androidboot.roc_logical_width=' + logical_width +
            ' androidboot.roc_logical_height=' + logical_height +
            ' androidboot.roc_rotation=' + str(metadata['display_rotation']) +
            ' androidboot.roc_panel_profile=' + str(profile))
    commands.update({
        'roc_lid0': 'setenv roc_clamshell 0',
        'roc_lid1': 'setenv roc_clamshell 1',
        'roc_boot_args': 'run roc_boot_args_${roc_active_model}',
        'roc_boot_kernel': 'bootm 45000000',
    })
    require(all(len(v.encode('ascii')) < 1024 and not any(t in v for t in (';', '&&', '\n'))
                for v in commands.values()), 'Simple-parser command size/control flow')
    require(all(len(v.split()) < 100 for v in commands.values()), 'Simple-parser argument limit')
    return commands


def patch_environment(block, dtb_offset):
    rows = decode_env(block)
    original = dict(rows)
    require(len(original) == len(rows), 'Duplicate env keys')
    require(original['boot_normal'] == 'sunxi_flash read 45000000 boot;bootm 45000000', 'Unexpected parent boot_normal')
    require(not any(k.startswith('roc_') for k in original), 'Already modified selector environment')
    changes = kernel_commands(dtb_offset)
    newrows = [(k, changes.get(k, v)) for k, v in rows]
    newrows += [(k, v) for k, v in changes.items() if k not in original]
    body = b'\0'.join((k + '=' + v).encode('ascii') if k else b'' for k, v in newrows) + b'\0\0'
    require(len(body) < ENV_SIZE - 4, 'Selector environment overflow')
    body = body.ljust(ENV_SIZE - 4, b'\0')
    result = struct.pack('<I', zlib.crc32(body)) + body
    after = dict(decode_env(result))
    require({k: v for k, v in after.items() if k not in changes} ==
            {k: v for k, v in original.items() if k not in changes}, 'Unrelated environment changed')
    return result, {'before_sha256': sha(block), 'after_sha256': sha(result),
                    'changed_variables': changes, 'saved_default': None}


def patch_ramdisk(original, menu, helper, hook):
    require(sha(menu) == MENU_SHA, 'Frozen native selector changed')
    require(menu[:6] == b'\x7fELF\x02\x01' and helper[:6] == b'\x7fELF\x02\x01', 'AArch64 ELFs required')
    require(struct.unpack_from('<H', menu, 18)[0] == struct.unpack_from('<H', helper, 18)[0] == 183,
            'AArch64 architecture required')
    old = parse(gzip.decompress(original))
    lookup = {e['name']: e for e in old}
    require(len(lookup) == len(old) and sha(lookup['init']['data']) == BASE_INIT_SHA,
            'Exact parent init/unique archive entries required')
    entries = copy.deepcopy(old)
    init = next(e for e in entries if e['name'] == 'init')
    needle = b'DATA_DEV=${TF1}p7\n'
    require(init['data'].count(needle) == 1, 'Unique selector handoff anchor required')
    call = (b'# Manual model choice runs before filesystem expansion and before Android.\n'
            b'if ! /bin/sh /grow/roc-selector-init.sh "$TF1"; then\n'
            b'    echo "[roc-selector] selector failed; preserving current panel and Android diagnostic boot"\n'
            b'fi\n')
    init['data'] = init['data'].replace(needle, needle + call)
    additions = {
        'grow/roc-boot-selector': menu,
        'grow/roc-boot-state': helper,
        'grow/roc-selector-init.sh': hook,
        'grow/ROC-SELECTOR-FONT-NOTICE.txt': (ROOT / 'out/boot-selector-integration-20261114/native/generated-v2/FONT-NOTICE.txt').read_bytes(),
    }
    for index, (name, data) in enumerate(additions.items()):
        require(name not in lookup, 'Selector payload already exists')
        item = dict(lookup['init'])
        item.update(name=name, ino=19000 + index, data=data,
                    mode=stat.S_IFREG | (0o644 if name.endswith('.txt') else 0o755), uid=0, gid=0, nlink=1)
        entries.insert(-1, item)
    changed = gzip.compress(b''.join(emit(e) for e in entries), compresslevel=6, mtime=0)
    after = {e['name']: e for e in parse(gzip.decompress(changed))}
    require(set(after) == set(lookup) | set(additions), 'Unexpected ramdisk entry set')
    for name, entry in lookup.items():
        require(after[name] == (init if name == 'init' else entry), 'Unexpected original ramdisk entry change: ' + name)
    return changed, {'before_sha256': sha(original), 'after_sha256': sha(changed),
                     'init_sha256': sha(init['data']),
                     'added': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in additions.items()}}


def integrate(shared, bridge_uboot, menu, helper, hook):
    require(len(shared) == PREFIX_BYTES, 'Expected complete shared prefix')
    output = bytearray(shared)
    toc = read_toc(shared[TOC_OFFSET:TOC_OFFSET + 1310720])
    uboot_item = next(i for i in toc['items'] if i['name'] == 'u-boot')
    ustart = TOC_OFFSET + uboot_item['offset']
    require(len(bridge_uboot) == uboot_item['bytes'] == 1048576, 'Unexpected early bridge U-Boot size')
    output[ustart:ustart + len(bridge_uboot)] = bridge_uboot
    before = shared[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES]
    old = parts(before)
    require(validate_profile(old['dtb']['data']) == 0, 'Default kernel profile must retain720')
    changed_rd, ramdisk = patch_ramdisk(old['ramdisk']['data'], menu, helper, hook)
    # Explicit v2 repack; preserve the header except ramdisk_size/dtb_size.
    header = bytearray(before[:2048])
    struct.pack_into('<I', header, 16, len(changed_rd))
    struct.pack_into('<I', header, 1648, old['dtb']['bytes'])
    boot = bytearray(header)
    for blob in (old['kernel']['data'], changed_rd, old['second']['data'], old['dtb']['data']):
        boot.extend(b'\0' * (align(len(boot)) - len(boot)))
        boot.extend(blob)
    boot.extend(b'\0' * (align(len(boot)) - len(boot)))
    used = len(boot)
    require(used < BOOT_BYTES, 'Repacked boot exceeds partition')
    require(set(before[old['end']:]) == {255}, 'Unknown non-erased boot tail')
    boot.extend(b'\xff' * (BOOT_BYTES - used))
    new = parts(boot)
    for name in ('kernel', 'second', 'dtb'):
        require(new[name]['data'] == old[name]['data'], 'Unexpected component change: ' + name)
    env, environment = patch_environment(shared[ENV_OFFSET:ENV_OFFSET + ENV_SIZE], new['dtb']['offset'])
    output[ENV_OFFSET:ENV_OFFSET + ENV_SIZE] = env
    output[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES] = boot
    output = toc_checksum(output)
    return output, {'schema': 2, 'supported_profiles': SUPPORTED,
        'default_model': 'rg35xxh', 'save_default': False,
        'first_boot': 'direct selector with the complete RG35XX H 640x480 profile; no key required',
        'reselect': 'volume-down during power-on forces selector and preserves the resolved panel',
        'model_metadata': MODEL_METADATA,
        'invalid_selection_fallback': 'legacy720 selector',
        'first_menu_visible_on_all_panels': False,
        'ramdisk': ramdisk, 'environment': environment,
        'boot_sha256': sha(boot), 'uboot_sha256': sha(bridge_uboot),
        'kernel_dtb_offset': new['dtb']['offset'], 'kernel_dtb_address': hex(0x45000000 + new['dtb']['offset']),
        'component_bytes': {name: new[name]['bytes'] for name in ('kernel', 'ramdisk', 'second', 'dtb')},
        'physical_display_accepted': False, 'all_H700_models_accepted': False}
