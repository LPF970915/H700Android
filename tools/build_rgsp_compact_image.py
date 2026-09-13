#!/usr/bin/env python3
"""Build a compact universal-card candidate from the proven v3b boot baseline.

This runs in WSL and only accepts regular local image files. No card writes.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import struct
import subprocess
import os
import zlib

from android_bootimg import read_header, component_offsets, pack
from patch_ramdisk import parse, emit
from audit_rgsp_single_card_boot import gpt, package

ROOT = Path(__file__).resolve().parents[1]
START = 28139585536
ROMS_SIZE = 4 * 1024**3
IMAGE_SIZE = START + ROMS_SIZE + 1536
DEX_SHA = "590718211152c842b9f13d508d96671e66134c806442e4f23b91cdc9a7e10ed2"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def compact_gpt(head, size):
    result = bytearray(head)
    gpt(result)
    table = bytearray(result[1024:2048])
    struct.pack_into("<Q", table, 7*128+40, size//512-4)
    def header(current, alternate, array):
        h = bytearray(result[512:1024])
        struct.pack_into("<QQQQ", h, 24, current, alternate, 4, size//512-4)
        struct.pack_into("<QIII", h, 72, array, 8, 128, zlib.crc32(table))
        struct.pack_into("<I", h, 16, 0)
        struct.pack_into("<I", h, 16, zlib.crc32(h[:92]))
        return h
    primary = header(1,size//512-1,2)
    tail = table + header(size//512-1,1,size//512-3)
    result[512:1024] = primary
    result[1024:2048] = table
    struct.pack_into("<I", result, 458, size//512-1)
    return result, tail


def copy_range(source, out, offset, count, dest=None):
    source.seek(offset)
    out.seek(offset if dest is None else dest)
    digest = hashlib.sha256()
    remaining = count
    while remaining:
        chunk = source.read(min(4*1024**2,remaining))
        if not chunk:
            raise ValueError("Source truncated")
        out.write(chunk)
        digest.update(chunk)
        remaining -= len(chunk)
        if (count-remaining) % (1024**3) == 0:
            print(f"COPY {count-remaining}/{count}",flush=True)
    return digest.hexdigest()


def ramdisk(prefix, build, runtime):
    original = bytes(prefix[148*1024**2:212*1024**2])
    template = build/"boot-template.img"
    template.write_bytes(original)
    _, h = read_header(template)
    offsets = component_offsets(h)
    start = offsets["ramdisk"]
    entries = parse(gzip.decompress(original[start:start+h["ramdisk_size"]]))
    old_names = {e["name"] for e in entries}
    init = next(e for e in entries if e["name"]=="init")
    text = init["data"].decode()
    marker = 'mount -t vfat -o rw "$ROMS_DEV" /single-card-roms ||'
    if text.count(marker)!=1:
        raise ValueError("Unexpected baseline init mount logic")
    text = text.replace(marker,
        '/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"\n\n'+marker)
    console_marker = 'mount -t devtmpfs devtmpfs /dev 2>/dev/null || true'
    text = text.replace(console_marker,console_marker+"""
if [ -c /dev/ttyS0 ]; then
    exec </dev/ttyS0 >/dev/ttyS0 2>&1
fi
echo '[rgsp-single-card] universal v5 ramdisk running'
""")
    init["data"] = text.encode()
    assert entries[-1]["name"] == "TRAILER!!!"
    entries = entries[:-1]
    old_names.remove("TRAILER!!!")
    def add(name, data=b"", directory=False):
        if name in old_names: raise ValueError("Unexpected duplicate ramdisk path")
        entries.append(dict(name=name, ino=30000+len(entries),
            mode=(stat.S_IFDIR|0o755) if directory else (stat.S_IFREG|0o755),
            uid=0,gid=0,nlink=1,mtime=0,data=data,devmajor=0,devminor=0,
            rdevmajor=0,rdevminor=0,check=0))
    add("grow",directory=True)
    add("grow/lib",directory=True)
    add("grow/auto-grow.sh",(ROOT/"tools/rgsp_auto_grow.sh").read_bytes())
    for name in ["rgsp-grow-gpt","rgsp-grow-fat"]:
        add("grow/"+name,(build/name).read_bytes())
    add("grow/fatlabel",(runtime/"usr/sbin/fatlabel").read_bytes())
    # Copy dependency SONAMEs as regular files, isolated from Android's Bionic.
    libs = ["ld-linux-aarch64.so.1","libc.so.6","libm.so.6","libparted.so.2",
        "libparted-fs-resize.so.0","libuuid.so.1","libblkid.so.1",
        "libdevmapper.so.1.02.1","libudev.so.1","libselinux.so.1",
        "libpcre2-8.so.0","libcap.so.2","libreadline.so.8","libtinfo.so.6"]
    for name in libs:
        add("grow/lib/"+name,(runtime/"usr/lib/aarch64-linux-gnu"/name).read_bytes())
    add("TRAILER!!!")
    archive = b"".join(emit(e) for e in entries)
    rebuilt = build/"ramdisk-v5.gz"
    rebuilt.write_bytes(gzip.compress(archive,compresslevel=6,mtime=0))
    boot = build/"boot-v5.img"
    pack(argparse.Namespace(template=str(template),out=str(boot),kernel=None,
        ramdisk=str(rebuilt),second=None,dtb=None))
    new = boot.read_bytes()
    _, hnew = read_header(boot)
    offnew = component_offsets(hnew)
    for name,length in [("kernel",h["kernel_size"]),("dtb",h["dt_size_detected"])]:
        assert original[offsets[name]:offsets[name]+length]==new[offnew[name]:offnew[name]+length]
    prefix[148*1024**2:212*1024**2] = new
    return prefix


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--system",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--build",type=Path,default=Path("/home/lpf/rgsp-grow-build"))
    parser.add_argument("--runtime",type=Path,default=Path("/home/lpf/rgsp-grow-runtime/runtime"))
    a=parser.parse_args()
    baseline=ROOT/"out/H700_Android_SingleCard_v3b.img"
    if a.output.exists() or a.output.with_suffix(".partial").exists():
        raise ValueError("New output paths required")
    if a.system.stat().st_size!=8589934592 or baseline.stat().st_size!=62239277056:
        raise ValueError("Unexpected source lengths")
    for path,offset in [(baseline,10959716352),(a.system,0)]:
        with path.open("rb") as f:
            f.seek(offset+1080)
            if f.read(2)!=b"\x53\xef": raise ValueError("Missing ext4 superblock: "+str(path))
    with baseline.open("rb") as f:
        prefix=bytearray(f.read(212*1024**2))
    if hashlib.sha256(prefix).hexdigest()!="bcca9ba02e60cb34843d88fbe69be77ce69d309e0d1096421e12829a4b5743f5":
        raise ValueError("Unrecognized proven prefix")
    before=package(prefix[32800*512:])
    prefix=ramdisk(prefix,a.build,a.runtime)
    prefix,tail=compact_gpt(prefix,IMAGE_SIZE)
    assert before==package(prefix[32800*512:])
    parts=gpt(prefix)
    if parts[-1]["start"]!=START: raise ValueError("Unexpected ROMS start")
    seed=a.build/"roms-seed.img"
    with seed.open("wb") as f: f.truncate(ROMS_SIZE)
    subprocess.run(["mkfs.fat","-F","32","-s","64","-n","ROMS",str(seed)],check=True)
    subprocess.run(["fsck.fat","-n",str(seed)],check=True)
    with seed.open("rb") as f:
        bs=f.read(512)
        reserved=struct.unpack_from("<H",bs,14)[0]
        fats=bs[16]*struct.unpack_from("<I",bs,36)[0]
        metadata=(reserved+fats+bs[13])*512
        f.seek(0)
        fat_head=f.read(metadata)
    partial=a.output.with_suffix(".partial")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    ranges=[]
    with partial.open("xb") as out, baseline.open("rb") as base, a.system.open("rb") as system:
        out.truncate(IMAGE_SIZE)
        out.write(prefix)
        ranges.append(dict(name="prefix",offset=0,bytes=len(prefix),sha256=hashlib.sha256(prefix).hexdigest()))
        for name,source,offset,count,dest in [
            ("system",system,0,8589934592,222298112),
            ("vendor",base,8812232704,2147483648,8812232704),
            ("data",base,10959716352,17179869184,10959716352)]:
            print("COPYING",name,flush=True)
            digest=copy_range(source,out,offset,count,dest)
            ranges.append(dict(name=name,offset=dest,bytes=count,sha256=digest))
        out.seek(START); out.write(fat_head)
        out.seek(IMAGE_SIZE-1536); out.write(tail)
        out.flush(); os.fsync(out.fileno())
    with partial.open("rb") as f:
        for offset in [222298112,8812232704,10959716352]:
            f.seek(offset+1080)
            assert f.read(2)==b"\x53\xef",f"Missing ext4 at {offset}"
    print("HASHING_COMPLETE_IMAGE",flush=True)
    digest=sha(partial)
    partial.rename(a.output)
    receipt=dict(status="BUILT_PENDING_OFFLINE_FSCK_AND_PHYSICAL_TEST",
        image=a.output.name,image_bytes=IMAGE_SIZE,sha256=digest,
        partitions=parts,ranges=ranges,at4k_dex_sha256=DEX_SHA,
        TV_UI_MODE_TYPE=4,auto_expand="GPT p8 plus FAT32, no formatting",
        hardware_vendor_source="v3b",data_source="v3b valid ext4",
        boot_package=before,physical_boot_verified=False)
    a.output.with_suffix(".json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=="__main__":
    main()
