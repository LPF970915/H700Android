"""Remap only the eight-entry H700 compact GPT; leave Boot0 at 8KiB intact."""
import struct
import uuid
import zlib
from audit_rgsp_single_card_boot import gpt

IMAGE_BYTES = 32434554368
NAMES = ['special', 'boot-resource', 'env', 'boot', 'system', 'vendor', 'data', 'ROMS']
STARTS = [37748736,104857600,138412032,155189248,222298112,8812232704,10959716352,28139585536]
LENGTHS = [67108864,33554432,16777216,67108864,8589934592,2147483648,17179869184,4294967296]

def prototype_gpt(head):
    """Return first 2KiB, final 1536B, and deterministic prototype PARTUUIDs.

    No block device is opened. A conventional 128-entry rewrite is forbidden:
    it would overlap the retained Allwinner Boot0 payload.
    """
    if len(head) != 2048 or head[510:512] != b'\x55\xaa' or head[450] != 0xee:
        raise ValueError('Unexpected compact protective MBR')
    parts = gpt(head)
    if struct.unpack_from('<QII', head, 512+72) != (2,8,128):
        raise ValueError('Require exactly eight compact entries at LBA2')
    expected = [dict(number=i+1,name=n,start=s,end_exclusive=s+l)
                for i,(n,s,l) in enumerate(zip(NAMES,STARTS,LENGTHS))]
    if parts != expected: raise ValueError('Unexpected hardware partition geometry')
    if struct.unpack_from('<QQQQ',head,512+24) != (1,IMAGE_BYTES//512-1,4,IMAGE_BYTES//512-4):
        raise ValueError('Unexpected compact image bounds')
    table = bytearray(head[1024:2048]); remap = {}
    seed = 'https://github.com/LPF970915/H700Android/dualabi-gsi10-p1-20261031/'
    disk = uuid.uuid5(uuid.NAMESPACE_URL, seed+'disk')
    for i,name in enumerate(NAMES):
        old = str(uuid.UUID(bytes_le=bytes(table[i*128+16:i*128+32])))
        new = uuid.uuid5(uuid.NAMESPACE_URL, seed+name)
        table[i*128+16:i*128+32] = new.bytes_le
        remap[name] = {'old_partuuid':old,'partuuid':str(new)}
    def header(current, alternate, entries):
        result=bytearray(head[512:1024])
        result[56:72]=disk.bytes_le
        struct.pack_into('<QQQQ',result,24,current,alternate,4,IMAGE_BYTES//512-4)
        struct.pack_into('<QIII',result,72,entries,8,128,zlib.crc32(table))
        struct.pack_into('<I',result,16,0)
        struct.pack_into('<I',result,16,zlib.crc32(result[:92]))
        return bytes(result)
    primary=head[:512]+header(1,IMAGE_BYTES//512-1,2)+table
    backup=table+header(IMAGE_BYTES//512-1,1,IMAGE_BYTES//512-3)
    if gpt(primary)!=parts: raise ValueError('Geometry changed during identity remap')
    if len(primary)!=2048 or len(backup)!=1536: raise ValueError('GPT range changed')
    return bytes(primary),bytes(backup),{'disk_guid':str(disk),'partitions':remap}


def relocate_gpt(head, card_bytes):
    """Relocate compact backup to the card end, without growing any filesystem.

    Return primary 2KiB and backup 1536B. Partition extents, type and unique
    GUIDs stay byte-identical; the caller must separately verify card identity.
    """
    gpt(head)
    if len(head)!=2048 or struct.unpack_from('<QII',head,584)!=(2,8,128):
        raise ValueError('Require compact eight-entry GPT')
    if card_bytes%512 or card_bytes<IMAGE_BYTES:raise ValueError('Unsupported card capacity')
    table=head[1024:2048];total=card_bytes//512
    primary=bytearray(head)
    struct.pack_into('<I',primary,458,min(total-1,0xffffffff))
    def header(current,alternate,entries):
        result=bytearray(head[512:1024])
        struct.pack_into('<QQQQ',result,24,current,alternate,4,total-4)
        struct.pack_into('<Q',result,72,entries)
        struct.pack_into('<I',result,16,0)
        struct.pack_into('<I',result,16,zlib.crc32(result[:92]))
        return bytes(result)
    primary[512:1024]=header(1,total-1,2)
    backup=table+header(total-1,1,total-3)
    if gpt(primary)!=gpt(head):raise ValueError('Partition extents changed during backup relocation')
    return bytes(primary),backup
