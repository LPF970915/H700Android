"""Pure byte transformations for ROC TF1; never opens a disk or makes an IMG."""
import struct
import uuid
import zlib

SEED_BYTES = 32434554368
DATA_START = 10959716352
DATA_MIN_BYTES = 17179869184
STARTS = [37748736, 104857600, 138412032, 155189248, 222298112, 8812232704, DATA_START]
LENGTHS = [67108864, 33554432, 16777216, 67108864, 8589934592, 2147483648]
NAMES = ['special', 'boot-resource', 'env', 'boot', 'system', 'vendor', 'userdata']
NAMESPACE = 'https://github.com/LPF970915/H700Android/roc-source64-unified-v1/'
DISK_GUID = uuid.uuid5(uuid.NAMESPACE_URL, NAMESPACE + 'disk').bytes_le
DATA_GUID = uuid.uuid5(uuid.NAMESPACE_URL, NAMESPACE + 'userdata').bytes_le
DATA_FS_UUID = uuid.uuid5(uuid.NAMESPACE_URL, NAMESPACE + 'userdata-filesystem')
LINUX_TYPE = uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le


def valid_header(header, table):
    if len(header) != 512 or len(table) != 1024:
        return False
    if header[:8] != b'EFI PART' or struct.unpack_from('<I', header, 12)[0] != 92:
        return False
    h = bytearray(header)
    expected = struct.unpack_from('<I', h, 16)[0]
    struct.pack_into('<I', h, 16, 0)
    return (zlib.crc32(h[:92]) == expected and
            struct.unpack_from('<II', h, 80) == (8, 128) and
            struct.unpack_from('<I', h, 88)[0] == zlib.crc32(table))


def headers(mbr, template, table, size):
    if size % 512 or size < SEED_BYTES:
        raise ValueError('Card cannot hold the seed layout')
    total = size // 512
    mbr = bytearray(mbr)
    struct.pack_into('<I', mbr, 458, min(total - 1, 0xffffffff))
    def header(here, other, entries):
        h = bytearray(template)
        h[56:72] = DISK_GUID
        struct.pack_into('<QQQQ', h, 24, here, other, 4, total - 4)
        struct.pack_into('<QIII', h, 72, entries, 8, 128, zlib.crc32(table))
        struct.pack_into('<I', h, 16, 0)
        struct.pack_into('<I', h, 16, zlib.crc32(h[:92]))
        return bytes(h)
    return bytes(mbr) + header(1, total - 1, 2) + bytes(table), bytes(table) + header(total - 1, 1, total - 3)


def derive(parent_head):
    if len(parent_head) != 2048 or parent_head[510:512] != b'\x55\xaa':
        raise ValueError('Require compact prefix metadata')
    h, table = parent_head[512:1024], bytearray(parent_head[1024:2048])
    if not valid_header(h, table) or struct.unpack_from('<Q', h, 72)[0] != 2:
        raise ValueError('Invalid compact GPT')
    # Pin all inherited extents before changing GUIDs or the tail layout.
    for i in range(7):
        start, end = struct.unpack_from('<QQ', table, i * 128 + 32)
        expected_length = LENGTHS[i] if i < 6 else DATA_MIN_BYTES
        oldname = table[i*128+56:i*128+128].decode('utf-16-le').split('\0')[0]
        if start * 512 != STARTS[i] or (end-start+1)*512 != expected_length or oldname != (NAMES[i] if i < 6 else 'data'):
            raise ValueError('Parent extent/name mismatch')
    for i, name in enumerate(NAMES):
        table[i*128+16:i*128+32] = uuid.uuid5(uuid.NAMESPACE_URL, NAMESPACE + name).bytes_le
    table[6*128:6*128+16] = LINUX_TYPE
    table[6*128+56:7*128] = 'userdata'.encode('utf-16-le').ljust(72, b'\0')
    struct.pack_into('<Q', table, 6*128+40, SEED_BYTES//512-4)
    table[7*128:8*128] = b'\0' * 128  # Keep the compact table footprint; no p8.
    return headers(parent_head[:512], h, table, SEED_BYTES)


def grow(head, size):
    h, table = head[512:1024], bytearray(head[1024:2048])
    if not valid_header(h, table) or h[56:72] != DISK_GUID:
        raise ValueError('Wrong source64 image')
    if table[6*128+16:6*128+32] != DATA_GUID or any(table[7*128:]):
        raise ValueError('Wrong userdata layout')
    if struct.unpack_from('<Q', table, 6*128+32)[0] != DATA_START//512:
        raise ValueError('Wrong userdata start')
    old_end = struct.unpack_from('<Q', table, 6*128+40)[0]
    if size % 512 or size < SEED_BYTES or size//512-4 < old_end:
        raise ValueError('Refuse truncation')
    struct.pack_into('<Q', table, 6*128+40, size//512-4)
    return headers(head[:512], h, table, size)


def c_identity():
    return ('#define ROC_DISK_GUID_BYTES {' + ','.join(str(x) for x in DISK_GUID) + '}\n'
            '#define ROC_DATA_GUID_BYTES {' + ','.join(str(x) for x in DATA_GUID) + '}\n'
            '#define ROC_DATA_FS_UUID_BYTES {' + ','.join(str(x) for x in DATA_FS_UUID.bytes) + '}\n'
            '#define ROC_LINUX_TYPE_BYTES {' + ','.join(str(x) for x in LINUX_TYPE) + '}\n')
