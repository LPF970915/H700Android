#!/usr/bin/env python3
"""Build a compact universal-card candidate from a hash-pinned local baseline.

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
DEX_SHA = "e54181a4c6b8149d65199abe4bbb4231109bb425ab92bf793b3d5f7eb2e948b9"
V5C_SHA = "cf481773dd2658a0a7307222f2a19679fd74c88a53923a0d72a13bfe7ef711cb"
V5C_PREFIX_SHA = "a6798b27211ebe1148cd4d2125eef6ae4c55e21aeccd588d937fe2a18338ebcb"
V5D_SHA = "96e31e46273dbe1882295e031e56bb3a7bb502b59482b26a09cf6db23cffc2e4"
V5D_PREFIX_SHA = "aaf0558ae5062c3698d116f546c85320336689e3bfc6952b4cc7305f7d8d3da6"
BASELINES = {
    "H700_Android_SingleCard_v5c_SettingsDpad.img": (V5C_SHA, V5C_PREFIX_SHA),
    "H700_Android_SingleCard_v5d_BootInput.img": (V5D_SHA, V5D_PREFIX_SHA),
}


def default_baseline():
    for name in BASELINES:
        path = ROOT/"out"/name
        if path.is_file():
            return path
    raise FileNotFoundError("No pinned v5c/v5d packaging baseline is available")


def baseline_identity(path):
    try:
        return BASELINES[path.name]
    except KeyError:
        raise ValueError("Unrecognized packaging baseline name") from None


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
    old_hook = '/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"\n'
    if text.count(old_hook) > 1:
        raise ValueError("Duplicate baseline grow hook")
    marker = 'mount -t vfat -o rw "$ROMS_DEV" /single-card-roms ||'
    if text.count(marker)!=1:
        raise ValueError("Unexpected baseline init mount logic")
    if 'ROMS_DEV=/dev/block/mmcblk0p8' in text:
        if text.count(old_hook) != 1:
            raise ValueError("Existing Android ROMS handoff requires one grow hook")
    else:
        text = text.replace(old_hook, "")
        text = text.replace(marker,
            old_hook+
            '# Android shutdown only enumerates /dev/block-backed mounts.\n'
            'mkdir -p /dev/block\n'
            'IFS=: read -r roms_major roms_minor < /sys/class/block/mmcblk0p8/dev\n'
            'ROMS_DEV=/dev/block/mmcblk0p8\n'
            'mknod "$ROMS_DEV" b "$roms_major" "$roms_minor" ||\n'
            '    fail "unable to create Android ROMS block node"\n\n'+marker)
    roms_bind = 'mount -o bind /single-card-roms /android-root/rgsp-persist'
    roms_move = 'mount -o move /single-card-roms /android-root/rgsp-persist'
    if text.count(roms_bind) + text.count(roms_move) != 1:
        raise ValueError("Unexpected baseline ROMS mount handoff")
    text = text.replace(roms_bind, roms_move)
    if "LOG=/android-root/rgsp-persist/RGSP_SINGLE_CARD_BOOT.log" not in text:
        text = text.replace(
            "echo '[rgsp-single-card] Android root ready; switching root' >> \"$LOG\"",
            "LOG=/android-root/rgsp-persist/RGSP_SINGLE_CARD_BOOT.log\n"
            "echo '[rgsp-single-card] Android root ready; switching root' >> \"$LOG\"")
    console_marker = 'mount -t devtmpfs devtmpfs /dev 2>/dev/null || true'
    if 'exec </dev/ttyS0 >/dev/ttyS0 2>&1' not in text:
        text = text.replace(console_marker,console_marker+"""
if [ -c /dev/ttyS0 ]; then
    exec </dev/ttyS0 >/dev/ttyS0 2>&1
fi
echo '[rgsp-single-card] universal v5 ramdisk running'
""")
    text = text.replace("universal v5 ramdisk running", "universal v5e ramdisk running")
    text = text.replace("universal v5d ramdisk running", "universal v5e ramdisk running")
    init["data"] = text.encode()
    assert entries[-1]["name"] == "TRAILER!!!"
    entries = entries[:-1]
    old_names.remove("TRAILER!!!")
    def add(name, data=b"", directory=False):
        if name in old_names:
            if name != "grow" and not name.startswith("grow/"):
                raise ValueError("Unexpected duplicate ramdisk path")
            entry = next(e for e in entries if e["name"] == name)
            if directory != stat.S_ISDIR(entry["mode"]):
                raise ValueError("Unexpected baseline grow entry type")
            if not directory:
                if not stat.S_ISREG(entry["mode"]):
                    raise ValueError("Refusing non-regular grow payload")
                entry["data"] = data
            return
        entries.append(dict(name=name, ino=30000+len(entries),
            mode=(stat.S_IFDIR|0o755) if directory else (stat.S_IFREG|0o755),
            uid=0,gid=0,nlink=1,mtime=0,data=data,devmajor=0,devminor=0,
            rdevmajor=0,rdevminor=0,check=0))
    add("grow",directory=True)
    add("grow/lib",directory=True)
    add("grow/auto-grow.sh",(ROOT/"tools/rgsp_auto_grow.sh").read_bytes())
    add("grow/check-fat.sh",(ROOT/"tools/rgsp_check_fat.sh").read_bytes())
    for name in ["rgsp-grow-gpt","rgsp-grow-fat"]:
        add("grow/"+name,(build/name).read_bytes())
    add("grow/fatlabel",(runtime/"usr/sbin/fatlabel").read_bytes())
    add("grow/fsck.fat",(runtime/"usr/sbin/fsck.fat").read_bytes())
    add("grow/lib/gconv",directory=True)
    add("grow/lib/gconv/gconv-modules",b"""alias CP850// IBM850//
alias 850// IBM850//
module IBM850// INTERNAL IBM850 1
module INTERNAL IBM850// IBM850 1
""")
    add("grow/lib/gconv/IBM850.so",
        (runtime/"usr/lib/aarch64-linux-gnu/gconv/IBM850.so").read_bytes())
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
    parser.add_argument("--baseline",type=Path)
    parser.add_argument("--build",type=Path,default=Path("/home/lpf/rgsp-grow-build"))
    parser.add_argument("--runtime",type=Path,default=Path("/home/lpf/rgsp-grow-runtime/runtime"))
    a=parser.parse_args()
    baseline=a.baseline or default_baseline()
    baseline_sha, prefix_sha = baseline_identity(baseline)
    if a.output.exists() or a.output.with_suffix(".partial").exists():
        raise ValueError("New output paths required")
    if a.system.stat().st_size!=8589934592 or baseline.stat().st_size!=IMAGE_SIZE:
        raise ValueError("Unexpected source lengths")
    for path in (a.system, baseline):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Only regular local image inputs are allowed")
    print("VERIFYING_BASELINE_SHA256", baseline.name, flush=True)
    if sha(baseline) != baseline_sha:
        raise ValueError("Baseline does not match its pinned full-image hash")
    for path,offset in [(baseline,10959716352),(a.system,0)]:
        with path.open("rb") as f:
            f.seek(offset+1080)
            if f.read(2)!=b"\x53\xef": raise ValueError("Missing ext4 superblock: "+str(path))
    with baseline.open("rb") as f:
        prefix=bytearray(f.read(212*1024**2))
    if hashlib.sha256(prefix).hexdigest()!=prefix_sha:
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
        hardware_vendor_source=baseline.name+" (preserved v3b hardware)",
        data_source=baseline.name+" empty ext4",
        baseline=dict(image=baseline.name,sha256=baseline_sha,prefix_sha256=prefix_sha),
        release="v5e AT4KDefault",
        boot_package=before,physical_boot_verified=False)
    a.output.with_suffix(".json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=="__main__":
    main()
