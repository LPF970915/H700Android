#!/usr/bin/env python3
"""Root-only RAM-disk/ROMS handoff test using a disposable Linux loop volume."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

from verify_rgsp_compact_image import verify_ramdisk, run, ROOT
from build_rgsp_compact_image import default_baseline

BUILD = Path(os.environ.get("RGSP_BOOT_TEST_BUILD", "/home/lpf/rgsp-v5d-build"))


def main():
    assert os.geteuid() == 0
    if "--inside" not in sys.argv:
        subprocess.run(["unshare", "--mount", "--propagation", "private",
                        sys.executable, __file__, "--inside"], check=True)
        return
    with default_baseline().open("rb") as stream:
        baseline = stream.read(212 * 1024**2)
    prefix = bytearray(baseline)
    prefix[148 * 1024**2:212 * 1024**2] = (BUILD/"boot-v5.img").read_bytes()
    with tempfile.TemporaryDirectory(prefix="boot-test-", dir=BUILD) as directory:
        temp = Path(directory)
        ram = verify_ramdisk(prefix, baseline, temp)
        command = ["qemu-aarch64", ram/"lib/ld-linux-aarch64.so.1",
                   "--library-path", ram/"lib", ram/"bin/busybox"]
        applets = set(run(*command, "--list").splitlines())
        assert {"sh", "od", "dd", "mknod", "mktemp", "cmp", "mount", "umount"} <= applets
        subprocess.run([sys.executable, "-m", "unittest", "test_rgsp_dirty_fat", "-v"],
                       cwd=ROOT/"tools", check=True,
                       env={**os.environ, "RGSP_TEST_ARM_RAMDISK": str(ram)})
        image = temp / "roms.img"
        with image.open("wb") as stream:
            stream.truncate(64 * 1024**2)
        run("mkfs.fat", "-F", "32", "-s", "1", "-n", "ROMS", image)
        loop = run("losetup", "--find", "--show", image).strip()
        assert loop.startswith("/dev/loop") and loop[9:].isdigit()
        alias = Path(f"/dev/block/rgsp-v5d-test-{os.getpid()}")
        old = temp / "single-card-roms"
        target = temp / "android-root/rgsp-persist"
        old.mkdir()
        target.mkdir(parents=True)
        created = False
        try:
            alias.parent.mkdir(exist_ok=True)
            os.mknod(alias, stat.S_IFBLK | 0o600, os.stat(loop).st_rdev)
            created = True
            run(*command, "mount", "-t", "vfat", "-o", "rw", alias, old)
            run(*command, "mount", "-o", "move", old, target)
            mounts = [line.split() for line in Path("/proc/mounts").read_text().splitlines()]
            assert not any(row[1] == str(old) for row in mounts)
            rows = [row for row in mounts if row[1] == str(target)]
            assert len(rows) == 1 and rows[0][0] == str(alias), rows
            assert rows[0][0].startswith("/dev/block/")
            (target/"roundtrip.txt").write_text("RGSP ROMS handoff fixture\n")
            run(*command, "sync")
            run(*command, "umount", target)
            run("fsck.fat", "-n", image)
            run("qemu-aarch64", ram/"lib/ld-linux-aarch64.so.1",
                "--library-path", ram/"lib", ram/"sbin/fsck.fat", "-n", image)
            with image.open("rb") as stream:
                stream.seek(65)
                assert stream.read(1) == b"\0"
            print("ARM_BUSYBOX_MOVE_ANDROID_BLOCK_PATH_AND_CLEAN_UNMOUNT_VERIFIED", flush=True)
        finally:
            mounts = {line.split()[1] for line in Path("/proc/mounts").read_text().splitlines()}
            for path in (target, old):
                if str(path) in mounts:
                    run("umount", path)
            try:
                # This BusyBox umount also detaches its loop-backed device.
                if run("losetup", "--associated", image).strip():
                    run("losetup", "--detach", loop)
            finally:
                if created:
                    alias.unlink()


if __name__ == "__main__":
    main()
