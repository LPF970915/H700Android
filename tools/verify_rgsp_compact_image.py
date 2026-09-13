#!/usr/bin/env python3
"""Read-only release gate for the complete raw image, run as root in WSL."""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

from android_bootimg import read_header, component_offsets
from audit_rgsp_single_card_boot import gpt, package
from patch_ramdisk import parse

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path("/home/lpf/rgsp-grow-build")
ANDROID = Path("/home/lpf/h700-android10/android")
DEX = "590718211152c842b9f13d508d96671e66134c806442e4f23b91cdc9a7e10ed2"
RES = "a20e44470f9e51121a6f7c2357cbc43e38ae5798aca3af57e5f2c66ebe69b236"
APK = "b6b2a3db335e5f2a27c284fc48ece6de9ccaf46a8886222aef07c17a26ee5d5b"


def sha(path, progress=False):
    with path.open("rb") as f:
        if progress:
            digest = hashlib.sha256()
            done = 0
            report = 0
            while chunk := f.read(4*1024**2):
                digest.update(chunk)
                done += len(chunk)
                if done-report >= 1024**3:
                    print(f"HASH {done}/{path.stat().st_size}", flush=True)
                    report = done
            return digest.hexdigest()
        return hashlib.file_digest(f, "sha256").hexdigest()


def run(*args, codes=(0,)):
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, env=env)
    shown = result.stdout if len(result.stdout) < 16000 else f"[{len(result.stdout)} characters parsed; dump suppressed]"
    print("$", *args, "\n", shown, result.stderr, flush=True)
    if result.returncode not in codes:
        raise RuntimeError(f"Verification command exited {result.returncode}")
    return result.stdout


@contextmanager
def volume(image, part):
    loop = run("losetup", "--find", "--show", "--read-only",
               "--offset", part["start"], "--sizelimit",
               part["end_exclusive"] - part["start"], image).strip()
    try:
        yield loop
    finally:
        run("losetup", "--detach", loop)


@contextmanager
def mounted(loop, root):
    root.mkdir()
    run("mount", "-t", "ext4", "-o", "ro,noload", loop, root)
    try:
        yield root
    finally:
        run("umount", root)


def verify_ramdisk(prefix, baseline, temp):
    boot = temp / "boot.img"
    boot.write_bytes(prefix[148*1024**2:212*1024**2])
    original = temp / "original.img"
    original.write_bytes(baseline[148*1024**2:212*1024**2])
    _, h = read_header(boot)
    _, old = read_header(original)
    offsets, old_offsets = component_offsets(h), component_offsets(old)
    b, o = boot.read_bytes(), original.read_bytes()
    for name, size in [("kernel", old["kernel_size"]),
                       ("second", old["second_size"]), ("dtb", old["dt_size_detected"])]:
        assert b[offsets[name]:offsets[name]+size] == o[old_offsets[name]:old_offsets[name]+size]
    for field in ["cmdline", "extra_cmdline", "kernel_addr", "ramdisk_addr", "page_size"]:
        assert h[field] == old[field], field
    entries = parse(gzip.decompress(b[offsets["ramdisk"]:offsets["ramdisk"]+h["ramdisk_size"]]))
    names = {e["name"]: e for e in entries}
    assert len(names) == len(entries)
    init = names["init"]["data"].decode()
    hook = '/bin/sh /grow/auto-grow.sh || fail "capacity preparation failed"'
    assert init.count(hook) == 1
    assert init.index(hook) < init.index('mount -t vfat')
    assert 'exec </dev/ttyS0 >/dev/ttyS0 2>&1' in init
    assert names["grow/auto-grow.sh"]["data"] == (ROOT/"tools/rgsp_auto_grow.sh").read_bytes()
    root = temp / "ramdisk"
    root.mkdir()
    for name, e in names.items():
        if not (name.startswith(("grow/", "lib/", "usr/lib/")) or name in
                ("bin/busybox", "sbin/fsck.fat", "lib64", "usr/lib64")):
            continue
        p = Path(name)
        assert not p.is_absolute() and ".." not in p.parts
        dest = root / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        mode = e["mode"]
        if stat.S_ISREG(mode):
            dest.write_bytes(e["data"])
            dest.chmod(mode & 0o777)
        elif stat.S_ISLNK(mode):
            target = e["data"].decode()
            assert not target.startswith("/")
            assert (dest.parent/target).resolve().is_relative_to(root.resolve())
            dest.symlink_to(target)
        elif stat.S_ISDIR(mode):
            dest.mkdir(exist_ok=True)
    for name in ["rgsp-grow-gpt", "rgsp-grow-fat"]:
        assert sha(root/"grow"/name) == sha(BUILD/name)
    run("qemu-aarch64", root/"lib/ld-linux-aarch64.so.1", "--library-path",
        root/"lib", root/"bin/busybox", "sh", "-n", root/"grow/auto-grow.sh")
    run("qemu-aarch64", root/"grow/lib/ld-linux-aarch64.so.1",
        "--library-path", root/"grow/lib", "--list", root/"grow/rgsp-grow-fat")
    return root


def verify_system(root):
    framework = root/"system/framework/framework-res.apk"
    output = run(ANDROID/"out/host/linux-x86/bin/aapt2", "dump", "resources", framework)
    for key, value in [("integer/config_defaultUiModeType", "4"),
                       ("bool/config_defaultInTouchMode", "false"),
                       ("bool/config_hasPermanentDpad", "true")]:
        assert re.search(r"resource [^\n]+ "+re.escape(key)+r"\n\s+\(\) "+value+r"\b", output), key
    apk = root/"system/priv-app/AT4K/AT4K.apk"
    assert sha(apk) == APK
    with zipfile.ZipFile(apk) as z:
        assert hashlib.sha256(z.read("classes.dex")).hexdigest() == DEX
        assert hashlib.sha256(z.read("resources.arsc")).hexdigest() == RES
    for installed, source in [
        ("system/bin/rgsp-firstboot.sh", "android/h700-android10/device/roc/rgsp/rgsp-firstboot.sh"),
        ("system/bin/set_rgsp_home.sh", "tools/set_rgsp_home.sh"),
        ("system/etc/init/rgsp-firstboot.rc", "android/h700-android10/device/roc/rgsp/rgsp-firstboot.rc")]:
        assert (root/installed).read_bytes() == (ROOT/source).read_bytes(), installed
    ime = root/"system/app/LeanbackIME/LeanbackIME.apk"
    assert sha(ime) == (root/"system/etc/rgsp/leanback.sha256").read_text().strip()
    for path in ["system/bin/init", "system/lib/modules/mali_kbase.ko",
                 "system/etc/init/rgsp_fix63_graphics.rc", "system/apex",
                 "system/usr/keylayout/ANBERNIC-keys.kl"]:
        assert (root/path).exists(), path
    for path, digest in {
        "system/lib/modules/mali_kbase.ko":
            "987e2feb5621f455c139c9e93c0c2a972f6eee0478b755b2cdfecfeb249970a9",
        "system/etc/init/rgsp_fix63_graphics.rc":
            "5511c62c415c33a80f309a91a01c8c694454a2dbbdde1472bb2d95ca9f60ed03",
        "system/usr/keylayout/ANBERNIC-keys.kl":
            "99b729a799e47db82a389527e4cc232e186d4a1c431f119326fb093a9def9056",
    }.items():
        assert sha(root/path) == digest, path
    for app in ["DocumentsUI", "Settings"]:
        assert list((root/"system").glob(f"**/{app}.apk")), app


def main():
    p = argparse.ArgumentParser()
    p.add_argument("image", type=Path)
    a = p.parse_args()
    assert os.geteuid() == 0, "Requires root for read-only loop mounts"
    assert a.image.is_file() and not a.image.is_symlink()
    manifest_path = a.image.with_suffix(".json")
    manifest = json.loads(manifest_path.read_text())
    assert a.image.stat().st_size == manifest["image_bytes"]
    run(BUILD/"grow-host", "--check", a.image, "--image-test")
    with a.image.open("rb") as f:
        prefix = f.read(212*1024**2)
    baseline = (ROOT/"out/rgsp-single-card-v3b-20260912/prefix-212m.bin").read_bytes()
    assert prefix[2048:148*1024**2] == baseline[2048:148*1024**2]
    assert package(prefix[32800*512:]) == package(baseline[32800*512:])
    parts = gpt(prefix)
    assert parts == manifest["partitions"]
    with tempfile.TemporaryDirectory(prefix="verify-", dir=BUILD) as temp:
        temp = Path(temp)
        ramroot = verify_ramdisk(prefix, baseline, temp)
        for part in parts[4:]:
            with volume(a.image, part) as loop:
                if part["name"] == "ROMS":
                    run("fsck.fat", "-n", loop)
                    run("qemu-aarch64", ramroot/"lib/ld-linux-aarch64.so.1", "--library-path",
                        ramroot/"lib", ramroot/"sbin/fsck.fat", "-n", loop)
                    run("qemu-aarch64", ramroot/"grow/lib/ld-linux-aarch64.so.1",
                        "--library-path", ramroot/"grow/lib",
                        ramroot/"grow/rgsp-grow-fat", loop, "--check")
                    continue
                run("e2fsck", "-f", "-n", loop)
                with mounted(loop, temp/part["name"]) as root:
                    if part["name"] == "system":
                        verify_system(root)
                    elif part["name"] == "data":
                        assert {x.name for x in root.iterdir()} <= {"lost+found"}
                    else:
                        for path in ["lib/egl/libGLES_mali.so", "modules/8821cs.ko",
                                     "etc/dispconfigs/h700-rgsp-lcd.json"]:
                            assert (root/path).exists(), path
    print("FULL_IMAGE_HASH_BEGIN", flush=True)
    assert sha(a.image, progress=True) == manifest["sha256"]
    manifest.update(status="OFFLINE_VERIFIED_READY_FOR_FLASH",
                    offline_checks=["GPT_CRC_AND_BOUNDS", "BOOT0_TOC_KERNEL_DTB_PRESERVED",
                                    "PACKED_RAMDISK_AND_ARM_RUNTIME", "FOUR_FILESYSTEMS_CLEAN",
                                    "TV_MODE_4_DPAD_TRUE_TOUCH_FALSE",
                                    "AT4K_ADAPTED_DEX_RESOURCES_AND_FACTORY_DEFAULT",
                                    "FULL_IMAGE_SHA256"],
                    physical_boot_verified=False)
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n")
    print("OFFLINE_VERIFIED_READY_FOR_FLASH", flush=True)


if __name__ == "__main__":
    main()
