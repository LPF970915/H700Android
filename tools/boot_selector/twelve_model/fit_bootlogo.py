"""Resize Test14's existing FAT16 bootlogo for all supported native framebuffers."""

import hashlib
import struct

ENTRY_BYTES = 32


def logo_entry(volume):
    # The vendor volume advertises a larger capacity than the partition. Only
    # follow the existing in-partition chain and keep both FAT mirrors consistent.
    sector, spc, reserved, copies, roots = struct.unpack_from('<HBHBH', volume, 11)
    fat_sectors = struct.unpack_from('<H', volume, 22)[0]
    assert (sector, spc, reserved, copies, roots, fat_sectors) == (512, 4, 1, 2, 512, 256)
    fats = [sector * (reserved + copy * fat_sectors) for copy in range(copies)]
    fat_size = fat_sectors * sector
    assert volume[fats[0]:fats[0]+fat_size] == volume[fats[1]:fats[1]+fat_size]
    root = fats[-1] + fat_size
    data = root + roots * ENTRY_BYTES
    entries = [i for i in range(root, data, ENTRY_BYTES) if volume[i:i+11] == b'BOOTLOGOBMP']
    assert len(entries) == 1
    row = entries[0]
    cluster, size = struct.unpack_from('<HI', volume, row + 26)
    block = sector * spc
    chain = []
    while cluster < 0xfff8:
        assert 2 <= cluster < 2 + (len(volume) - data) // block and cluster not in chain
        chain.append(cluster)
        cluster = struct.unpack_from('<H', volume, fats[0] + 2 * cluster)[0]
    assert len(chain) == (size + block - 1) // block
    offsets = [data + (c - 2) * block for c in chain]
    bmp = b''.join(volume[o:o+block] for o in offsets)[:size]
    return bmp, row, fats, block, chain, offsets


def fit_bootlogo(volume):
    bmp, row, fats, block, chain, offsets = logo_entry(volume)
    assert bmp[:2] == b'BM' and struct.unpack_from('<IIiiHHI', bmp, 10) == (54, 40, 720, 480, 1, 24, 0)
    width, height = 480, 320
    new = bytearray(bmp[:54]) + bytearray(width * height * 3)
    struct.pack_into('<I', new, 2, len(new))
    struct.pack_into('<ii', new, 18, width, height)
    struct.pack_into('<I', new, 34, len(new) - 54)
    # Area-average the 3:2 shrink. Each output pixel covers 1.5 x 1.5
    # original pixels, with integer weights summing to nine.
    for y in range(height):
        y0, fy = divmod(3*y, 2)
        wy = 2 - fy
        for x in range(width):
            x0, fx = divmod(3*x, 2)
            wx = 2 - fx
            a = 54 + 3 * (720*y0 + x0)
            b = a + 720*3
            dest = 54 + 3 * (width*y + x)
            for channel in range(3):
                top = wx*bmp[a+channel] + (3-wx)*bmp[a+3+channel]
                bottom = wx*bmp[b+channel] + (3-wx)*bmp[b+3+channel]
                new[dest+channel] = (wy*top + (3-wy)*bottom + 4) // 9
    output = bytearray(volume)
    used = (len(new) + block - 1) // block
    for i, offset in enumerate(offsets[:used]):
        chunk = new[i*block:(i+1)*block]
        output[offset:offset+len(chunk)] = chunk
    for fat in fats:
        struct.pack_into('<H', output, fat + 2*chain[used-1], 0xffff)
        for cluster in chain[used:]:
            struct.pack_into('<H', output, fat + 2*cluster, 0)
    struct.pack_into('<I', output, row + 28, len(new))
    readback, *_ = logo_entry(output)
    assert readback == new
    return bytes(output), dict(source_sha256=hashlib.sha256(bmp).hexdigest(),
                               sha256=hashlib.sha256(new).hexdigest(), old_size=[720,480],
                               size=[width,height], file_bytes=len(new))
