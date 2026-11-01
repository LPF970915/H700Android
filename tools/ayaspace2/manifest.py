"""Narrow binary XML edits, preserving all unrelated resource indexes/bytes."""
import struct

def u32(b, at): return struct.unpack_from('<I', b, at)[0]
def u16(b, at): return struct.unpack_from('<H', b, at)[0]
def put32(b, at, value): struct.pack_into('<I', b, at, value)
def put16(b, at, value): struct.pack_into('<H', b, at, value)

class Pool:
    def __init__(self, data):
        self.data = bytearray(data)
        self.count, self.styles, self.flags, self.start, self.style_start = struct.unpack_from('<5I', data, 8)
        assert self.styles == 0 and self.style_start == 0
        self.strings = []
        self.offsets = [u32(data, 28 + 4*i) for i in range(self.count)]
        for offset in self.offsets:
            p = self.start + offset
            if self.flags & 0x100:
                _, p = self.length(data, p, 1)
                n, p = self.length(data, p, 1)
                self.strings.append(data[p:p+n].decode('utf8'))
            else:
                n, p = self.length(data, p, 2)
                self.strings.append(data[p:p+2*n].decode('utf-16-le'))
        self.extra = bytearray()
    @staticmethod
    def length(data, p, width):
        value = data[p] if width == 1 else u16(data, p)
        mask = 0x80 if width == 1 else 0x8000
        if value & mask:
            low = data[p+width] if width == 1 else u16(data, p+width)
            return ((value & ~mask) << (8*width)) | low, p+2*width
        return value, p+width
    def add(self, value):
        if value in self.strings: return self.strings.index(value)
        raw = value.encode('utf8' if self.flags & 0x100 else 'utf-16-le')
        assert len(raw) < 128 and len(value) < 128
        self.offsets.append(len(self.data)-self.start+len(self.extra))
        if self.flags & 0x100:
            self.extra.extend(bytes([len(value), len(raw)]) + raw + b'\0')
        else:
            self.extra.extend(struct.pack('<H', len(raw)//2)+raw+b'\0\0')
        self.strings.append(value)
        return len(self.strings)-1
    def emit(self):
        head = bytearray(self.data[:28])
        put32(head, 8, len(self.strings))
        put32(head, 16, self.flags & ~1)  # appended pool is not sorted
        put32(head, 20, 28+4*len(self.offsets))
        result = head + struct.pack('<%dI' % len(self.offsets), *self.offsets) + self.data[self.start:] + self.extra
        result.extend(b'\0' * (-len(result) % 4))
        put32(result, 4, len(result))
        return result

def patch(source, revision):
    assert u16(source, 0) == 3 and u32(source, 4) == len(source)
    chunks=[];p=8
    while p<len(source):
        size=u32(source,p+4);assert size>=8;chunks.append(bytearray(source[p:p+size]));p+=size
    pool=Pool(bytes(chunks[0]));log=[];result=[];template=None;permission_end=None
    for chunk in chunks[1:]:
        kind=u16(chunk,0)
        if kind==0x102:
            tag=pool.strings[u32(chunk,20)]
            start=16+u16(chunk,24);stride=u16(chunk,26);count=u16(chunk,28)
            assert stride==20
            attrs=[bytearray(chunk[start+stride*i:start+stride*(i+1)]) for i in range(count)]
            kept=[]
            for attr in attrs:
                name=pool.strings[u32(attr,4)]
                if tag=='manifest' and name=='sharedUserId':
                    log.append('remove sharedUserId android.uid.system');continue
                if tag=='uses-sdk' and name in ('minSdkVersion','targetSdkVersion'):
                    put32(attr,16,29);log.append(name+'=29')
                if tag=='application' and name=='requestLegacyExternalStorage':
                    put32(attr,16,0xffffffff);log.append('requestLegacyExternalStorage=true')
                if tag=='manifest' and name=='versionName':
                    index=pool.add('0.3.3-a10-h700-r'+str(revision));put32(attr,8,index);put32(attr,16,index)
                kept.append(attr)
            chunk=chunk[:start]+b''.join(kept)+chunk[start+count*stride:]
            put16(chunk,28,len(kept));put32(chunk,4,len(chunk))
            if tag=='uses-permission' and template is None: template=bytes(chunk)
        result.append(chunk)
        if kind==0x103 and pool.strings[u32(chunk,20)]=='uses-permission' and permission_end is None:
            permission_end=bytes(chunk)
            for permission in ('android.permission.READ_EXTERNAL_STORAGE','android.permission.WRITE_EXTERNAL_STORAGE'):
                new=bytearray(template);index=pool.add(permission);start=16+u16(new,24)
                assert u16(new,28)==1
                put32(new,start+8,index);put32(new,start+16,index)
                result.extend([new,bytearray(permission_end)]);log.append('add '+permission)
    assert len(log)==6,log
    blob=bytearray(source[:8])+pool.emit()+b''.join(result);put32(blob,4,len(blob))
    return bytes(blob),log
