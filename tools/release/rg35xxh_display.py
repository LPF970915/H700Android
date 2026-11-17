"""Explicit RG35XX H test profile for exact ROC OS 0.0.2 boot bytes.

This is a model-specific experiment, not automatic panel detection. The
withdrawn old/boe geometry heuristic is never imported or re-enabled.
"""
from pathlib import Path
import hashlib
import struct
import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from audit_rgsp_single_card_boot import package as read_toc

PANEL = '/soc@03000000/lcd0@01c0c000'
TOC_OFFSET = 16793600
TOC_BYTES = 1310720
BOOT_OFFSET = 155189248
BOOT_BYTES = 67108864
PREFIX_BYTES = 222298112
BASE_BOOT_SHA = '4a28d5f1ed27cd603a45a022b46de5e7eb49eec6755b4c129b51d630bce1b383'
BASE_TOC_SHA = '957929afa2879e18ff758d93eafa98879b21aec70dedcb731d7862a2c20f075c'
BASE_BOOT_DTB_SHA = '7185c0b78f521cb7e187943bb4652378898771828d524c75e1d262617ee7b045'
SOURCE = {
    'lcd_x': 720, 'lcd_y': 480, 'lcd_dclk_freq': 26, 'lcd_hbp': 46,
    'lcd_ht': 820, 'lcd_hspw': 2, 'lcd_vbp': 20, 'lcd_vt': 536,
    'lcd_vspw': 5, 'lcd_hv_clk_phase': 1, 'lcd_hv_sync_polarity': 3,
}
TARGET = {
    'lcd_x': 640, 'lcd_y': 480, 'lcd_dclk_freq': 24, 'lcd_hbp': 46,
    'lcd_ht': 770, 'lcd_hspw': 20, 'lcd_vbp': 15, 'lcd_vt': 520,
    'lcd_vspw': 4, 'lcd_hv_clk_phase': 2, 'lcd_hv_sync_polarity': 3,
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fdt_properties(blob):
    """Return raw property bytes and offsets, preserving every unrelated byte."""
    require(len(blob) >= 40, 'Short FDT')
    magic, total, structs, strings, reserve, version, compat, cpu, strings_len, structs_len = struct.unpack_from('>10I', blob)
    require(magic == 0xd00dfeed and total <= len(blob), 'Invalid FDT header')
    require(version == 17 and compat <= 17, 'Unexpected FDT version')
    require(40 <= structs < total and 40 <= strings < total, 'FDT offsets outside blob')
    require(structs + structs_len <= total and strings + strings_len <= total, 'FDT sections outside blob')
    pos, stack, props, finished = structs, [], {}, False
    struct_end = structs + structs_len
    while pos + 4 <= struct_end:
        token = struct.unpack_from('>I', blob, pos)[0]
        pos += 4
        if token == 1:
            end = blob.find(b'\0', pos, struct_end)
            require(end >= pos, 'Unterminated FDT node')
            stack.append(blob[pos:end].decode('ascii'))
            pos = (end + 4) & ~3
        elif token == 2:
            require(stack, 'FDT node stack underflow')
            stack.pop()
        elif token == 3:
            require(stack and pos + 8 <= struct_end, 'Truncated FDT property')
            size, name_offset = struct.unpack_from('>II', blob, pos)
            pos += 8
            require(pos + size <= struct_end and name_offset < strings_len, 'FDT property outside section')
            end = blob.find(b'\0', strings + name_offset, strings + strings_len)
            require(end >= strings + name_offset, 'Unterminated FDT property name')
            name = blob[strings + name_offset:end].decode('ascii')
            path = '/' + '/'.join(part for part in stack if part)
            key = path + '/' + name
            require(key not in props, 'Duplicate FDT property: ' + key)
            props[key] = {'offset': pos, 'data': blob[pos:pos+size]}
            pos = (pos + size + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            require(not stack, 'Unclosed FDT nodes')
            finished = True
            break
        else:
            raise ValueError('Unknown FDT token')
    require(finished, 'FDT end token absent')
    return total, props


def patch_lcd(blob):
    total, before = fdt_properties(blob)
    driver = before[PANEL + '/lcd_driver_name']['data']
    require(driver == b'rg34xxsp_v1\0', 'Unexpected registered panel alias')
    output, changes = bytearray(blob), []
    for name, target in TARGET.items():
        prop = before[PANEL + '/' + name]
        require(prop['data'] == struct.pack('>I', SOURCE[name]), 'Unexpected source LCD value: ' + name)
        if target == SOURCE[name]:
            continue
        offset = prop['offset']
        output[offset:offset+4] = struct.pack('>I', target)
        changes.append({'property': name, 'offset': offset, 'bytes': 4,
                        'before': SOURCE[name], 'after': target})
    _, after = fdt_properties(bytes(output))
    changed_keys = {key for key in before if before[key]['data'] != after[key]['data']}
    require(changed_keys == {PANEL + '/' + row['property'] for row in changes}, 'Unexpected FDT property delta')
    require(before.keys() == after.keys() and len(output) == len(blob), 'FDT layout changed')
    for row in changes:
        require(after[PANEL + '/' + row['property']]['offset'] == row['offset'], 'FDT offset changed')
    require(output[total:] == blob[total:], 'FDT item padding changed')
    return bytes(output), changes


def boot_dtb_location(boot):
    require(len(boot) == BOOT_BYTES and boot[:8] == b'ANDROID!', 'Unexpected boot partition')
    kernel, ramdisk, second = (struct.unpack_from('<I', boot, p)[0] for p in (8, 16, 24))
    page = struct.unpack_from('<I', boot, 36)[0]
    require(page == 2048 and struct.unpack_from('<I', boot, 40)[0] == 2, 'Unexpected Android boot header')
    align = lambda n: (n + page - 1) // page * page
    offset = page + align(kernel) + align(ramdisk) + align(second)
    require(offset == 22081536, 'Unexpected boot DTB offset')
    total, _ = fdt_properties(boot[offset:])
    require(total == 137564, 'Unexpected boot DTB length')
    return offset, total


def patch_prefix(prefix):
    require(len(prefix) == PREFIX_BYTES, 'Unexpected prefix size')
    boot = prefix[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES]
    require(sha(boot) == BASE_BOOT_SHA, 'Expected exact 0.0.2 boot')
    dtb_offset, dtb_size = boot_dtb_location(boot)
    require(sha(boot[dtb_offset:dtb_offset+dtb_size]) == BASE_BOOT_DTB_SHA, 'Boot DTB identity mismatch')
    toc = prefix[TOC_OFFSET:TOC_OFFSET + TOC_BYTES]
    require(sha(toc) == BASE_TOC_SHA, 'TOC identity mismatch')
    toc_meta = read_toc(toc)
    require(toc_meta['bytes'] == TOC_BYTES, 'TOC length mismatch')
    item = next(row for row in toc_meta['items'] if row['name'] == 'dtb')
    toc_dtb_start, toc_dtb_size = item['offset'], item['bytes']
    require(toc_dtb_start == 1161216 and toc_dtb_size == 143872, 'Unexpected TOC DTB placement')
    toc_dtb = toc[toc_dtb_start:toc_dtb_start + toc_dtb_size]
    total, _ = fdt_properties(toc_dtb)
    require(total == 139616, 'Unexpected U-Boot FDT length')
    # The complete TOC hash already authenticates this region and its padding.
    patched_early, early_changes = patch_lcd(toc_dtb)
    patched_boot, boot_changes = patch_lcd(boot[dtb_offset:dtb_offset + dtb_size])
    output = bytearray(prefix)
    early_base = TOC_OFFSET + toc_dtb_start
    output[early_base:early_base + toc_dtb_size] = patched_early
    kernel_base = BOOT_OFFSET + dtb_offset
    output[kernel_base:kernel_base + dtb_size] = patched_boot
    # TOC1 integrity uses an additive checksum with the checksum field stamped.
    struct.pack_into('<I', output, TOC_OFFSET + 20, 0x5f0a6c39)
    checksum = sum(struct.unpack_from('<' + str(TOC_BYTES // 4) + 'I', output, TOC_OFFSET)) & 0xffffffff
    struct.pack_into('<I', output, TOC_OFFSET + 20, checksum)
    after_toc = read_toc(output[TOC_OFFSET:TOC_OFFSET + TOC_BYTES])
    before_items = {row['name']: row for row in toc_meta['items']}
    for row in after_toc['items']:
        if row['name'] != 'dtb':
            require(row == before_items[row['name']], 'TOC executable/item changed')
    spans = [{'offset': TOC_OFFSET + 20, 'bytes': 4, 'component': 'toc_checksum'}]
    for base, rows, component in [(early_base, early_changes, 'uboot_dtb'), (kernel_base, boot_changes, 'kernel_dtb')]:
        spans.extend(dict(row, offset=base + row['offset'], component=component) for row in rows)
    cursor = 0
    for row in sorted(spans, key=lambda row: row['offset']):
        require(output[cursor:row['offset']] == prefix[cursor:row['offset']], 'Unexpected prefix byte changed')
        cursor = row['offset'] + row['bytes']
    require(output[cursor:] == prefix[cursor:], 'Unexpected prefix suffix changed')
    require(sha(output[BOOT_OFFSET:BOOT_OFFSET+BOOT_BYTES]) != BASE_BOOT_SHA, 'No boot change')
    return bytes(output), {'profile': 'explicit-rg35xx-h-640x480', 'automatic_detection': False,
                           'selected_lcd_properties': TARGET, 'registered_alias_retained': driver_name(output, kernel_base),
                           'allowed_changed_spans': sorted(spans, key=lambda row: row['offset']),
                           'changed_byte_count': sum(a != b for a, b in zip(prefix, output)),
                           'toc_checksum_valid': True, 'toc_items_after': after_toc['items'],
                           'boot_sha256': sha(output[BOOT_OFFSET:BOOT_OFFSET+BOOT_BYTES]),
                           'kernel_dtb_sha256': sha(patched_boot), 'uboot_dtb_sha256': sha(patched_early[:total])}


def driver_name(prefix, offset):
    _, props = fdt_properties(prefix[offset:])
    return props[PANEL + '/lcd_driver_name']['data'].rstrip(b'\0').decode('ascii')
