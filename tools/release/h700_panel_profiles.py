"""Bounded FDT carrier for one shared H700 image.

This module edits ordinary FDT byte strings only.  It has no physical disk,
device, whole-image, compression or model-detection entry point.  Profile0
retains the working720 path; profile1 explicitly requests the pinned35H path.
The early loader and kernel consumers must exist before this is deliverable.
"""
import hashlib
import struct

from rg35xxh_display import PANEL, SOURCE, TARGET, fdt_properties

PROPERTY = 'roc_panel_profile'
KEY = PANEL + '/' + PROPERTY
PROFILES = {0: 'retained720', 1: 'rg35xx-h'}
TIMINGS = {0: dict(SOURCE), 1: dict(TARGET)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def header(blob):
    require(len(blob) >= 40, 'Short FDT')
    fields = list(struct.unpack_from('>10I', blob))
    require(fields[0] == 0xd00dfeed and fields[5] == 17, 'Expected v17 FDT')
    require(40 <= fields[1] <= len(blob), 'FDT total outside supplied capacity')
    return fields


def node_start(blob, path):
    """Locate the first property position, before any original child/property."""
    fields = header(blob)
    pos, limit, stack, result = fields[2], fields[2] + fields[9], [], []
    while pos + 4 <= limit:
        token, = struct.unpack_from('>I', blob, pos)
        pos += 4
        if token == 1:
            end = blob.find(b'\0', pos, limit)
            require(end >= pos, 'Unterminated node name')
            stack.append(blob[pos:end].decode('ascii'))
            pos = (end + 4) & ~3
            if '/' + '/'.join(x for x in stack if x) == path:
                result.append(pos)
        elif token == 2:
            require(stack, 'Node stack underflow')
            stack.pop()
        elif token == 3:
            require(pos + 8 <= limit, 'Truncated property header')
            size, name = struct.unpack_from('>II', blob, pos)
            require(name < fields[8], 'Property string outside table')
            pos = (pos + 8 + size + 3) & ~3
            require(pos <= limit, 'Property outside structure')
        elif token == 4:
            pass
        elif token == 9:
            require(not stack, 'Unclosed FDT nodes')
            break
        else:
            raise ValueError('Unexpected FDT token')
    require(len(result) == 1, 'Expected exactly one panel node')
    return result[0]


def add_carrier(blob, *, keep_total):
    """Insert one uint32 property using caller-supplied zero slack only.

    Existing reserve map and all properties are retained byte-for-byte.  A
    caller handling an Android boot header must separately update dtb_size
    when keep_total=False; this function cannot touch any enclosing image.
    """
    fields = header(blob)
    total, props = fdt_properties(blob)
    require(KEY not in props, 'Profile carrier already exists')
    require(props[PANEL + '/lcd_driver_name']['data'] == b'rg34xxsp_v1\0',
            'Unexpected registered panel driver')
    for name, value in SOURCE.items():
        require(props[PANEL + '/' + name]['data'] == struct.pack('>I', value),
                'Only the exact retained720 timings can seed a shared image')
    struct_start, strings_start = fields[2], fields[3]
    struct_end = struct_start + fields[9]
    strings_end = strings_start + fields[8]
    require(struct_end == strings_start, 'Noncontiguous original sections')
    require(strings_end <= total and not any(blob[strings_end:total]),
            'Only existing zero slack may be consumed')
    name = PROPERTY.encode('ascii') + b'\0'
    record = struct.pack('>4I', 3, 4, fields[8], 0)
    insert = node_start(blob, PANEL)
    require(struct_start <= insert < struct_end, 'Panel insertion outside structure')
    minimum = strings_end + len(record) + len(name)
    new_total = total if keep_total else (minimum + 3) & ~3
    require(minimum <= new_total <= len(blob), 'Insufficient FDT zero capacity')
    require(not any(blob[total:new_total]), 'Nonzero enclosing padding cannot be consumed')
    output = bytearray(blob)
    structure = blob[struct_start:insert] + record + blob[insert:struct_end]
    strings = blob[strings_start:strings_end] + name
    new_strings = struct_start + len(structure)
    output[struct_start:new_total] = (structure + strings).ljust(new_total - struct_start, b'\0')
    fields[1], fields[3] = new_total, new_strings
    fields[8] += len(name)
    fields[9] += len(record)
    struct.pack_into('>10I', output, 0, *fields)
    new_total_check, after = fdt_properties(output)
    require(new_total_check == new_total, 'Unexpected total after insertion')
    require(set(after) == set(props) | {KEY}, 'Unexpected property set change')
    require(all(after[key]['data'] == row['data'] for key, row in props.items()),
            'Original FDT property changed')
    require(after[KEY]['data'] == b'\0' * 4, 'Default must retain720')
    require(output[40:struct_start] == blob[40:struct_start], 'Reserve map/prefix changed')
    require(output[new_total:] == blob[new_total:], 'Outside FDT changed')
    return bytes(output), {
        'profile_property': KEY, 'profile': 0, 'automatic_identity': False,
        'old_total': total, 'new_total': new_total,
        'old_properties': len(props), 'new_properties': len(after),
        'profile_data_offset': after[KEY]['offset'],
        'capacity': len(blob), 'before_sha256': digest(blob),
        'after_sha256': digest(output), 'original_properties_preserved': True,
    }


def read_profile(blob):
    _, props = fdt_properties(blob)
    require(KEY in props and len(props[KEY]['data']) == 4, 'Invalid/missing profile carrier')
    return struct.unpack('>I', props[KEY]['data'])[0]


def validate_profile(blob):
    """Require one supported, internally consistent configured tree."""
    profile = read_profile(blob)
    require(profile in PROFILES, 'Unknown configured profile')
    _, props = fdt_properties(blob)
    require(props[PANEL + '/lcd_driver_name']['data'] == b'rg34xxsp_v1\0',
            'Unexpected registered driver')
    for name, value in TIMINGS[profile].items():
        require(props[PANEL + '/' + name]['data'] == struct.pack('>I', value),
                'Profile/timing mismatch: ' + name)
    return profile


def select_profile(blob, profile):
    """Configure the full explicit profile before any display parameter parse.

    The same shared image carries both init programs. First selection configures
    its FDT carrier and all eleven numeric properties together. Merely changing
    an integer carrier would leave an inconsistent scan timing configuration.
    """
    require(type(profile) is int and profile in PROFILES, 'Unsupported explicit profile')
    current = validate_profile(blob)
    _, before = fdt_properties(blob)
    output = bytearray(blob)
    allowed = {KEY: profile}
    allowed.update({PANEL + '/' + name: value for name, value in TIMINGS[profile].items()})
    for key, value in allowed.items():
        require(len(before[key]['data']) == 4, 'Non-u32 profile field')
        struct.pack_into('>I', output, before[key]['offset'], value)
    cursor = 0
    for position in sorted(before[key]['offset'] for key in allowed):
        require(output[cursor:position] == blob[cursor:position], 'Unrelated profile bytes changed')
        cursor = position + 4
    require(output[cursor:] == blob[cursor:], 'Unrelated profile suffix changed')
    require(validate_profile(output) == profile, 'Explicit selection readback failed')
    return bytes(output)


def validate_pair(early, kernel):
    """Reject split explicit choices before constructing an enclosing artifact."""
    left, right = validate_profile(early), validate_profile(kernel)
    require(left == right, 'Early/kernel profile mismatch')
    return left
