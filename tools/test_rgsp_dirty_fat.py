"""Real dosfstools checks against disposable regular-file FAT32 fixtures."""
import hashlib
import gzip
import os
from pathlib import Path
import shutil
import shlex
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("fsck.fat") and shutil.which("mkfs.fat"),
                     "dosfstools required")
class DirtyFatTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.volume = self.root / "roms.img"
        with self.volume.open("wb") as stream:
            stream.truncate(64 * 1024**2)
        subprocess.run(["mkfs.fat", "-F", "32", "-s", "1", "-n", "ROMS",
                        str(self.volume)], check=True, capture_output=True)
        self.state = self.root / "state"
        self.state.mkdir()
        script = (ROOT / "tools/rgsp_check_fat.sh").read_text()
        script = script.replace("/dev/mmcblk0p8", str(self.volume))
        script = script.replace('[ -b "$roms" ]', '[ -f "$roms" ]')
        arm = os.environ.get("RGSP_TEST_ARM_RAMDISK")
        fsck = shutil.which("fsck.fat")
        od = "od"
        if arm:
            ram = Path(arm)
            fsck = shlex.join(["qemu-aarch64", str(ram/"grow/lib/ld-linux-aarch64.so.1"),
                              "--library-path", str(ram/"grow/lib"), str(ram/"grow/fsck.fat")])
            od = shlex.join(["qemu-aarch64", str(ram/"lib/ld-linux-aarch64.so.1"),
                            "--library-path", str(ram/"lib"), str(ram/"bin/busybox"), "od"])
            script = script.replace("export GCONV_PATH=/grow/lib/gconv",
                                    "export GCONV_PATH=" + shlex.quote(str(ram/"grow/lib/gconv")))
        else:
            script = script.replace("export GCONV_PATH=/grow/lib/gconv", "unset GCONV_PATH")
        script = script.replace(
            "/grow/lib/ld-linux-aarch64.so.1 --library-path /grow/lib \\\n"
            "        /grow/fsck.fat", fsck)
        script = script.replace("/bin/busybox od", od)
        script = script.replace("/tmp/rgsp-fat-check.", str(self.root / "check."))
        self.script = self.root / "check.sh"
        self.script.write_text(script)

    def write_at(self, offset, data):
        with self.volume.open("r+b") as stream:
            stream.seek(offset)
            stream.write(data)

    def digest(self):
        with self.volume.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    def run_check(self):
        return subprocess.run(["sh", str(self.script), str(self.volume), str(self.state)],
                              capture_output=True, text=True, timeout=60)

    def test_clean_unchanged_and_no_repair_backup(self):
        before = self.digest()
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.digest(), before)
        self.assertEqual(list(self.state.iterdir()), [])

    def test_dirty_only_matches_original_and_repeat_is_noop(self):
        clean = self.digest()
        self.write_at(65, b"\x01")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.digest(), clean)
        backup, = self.state.iterdir()
        before = (backup / "boot-sector.before").read_bytes()
        after = (backup / "boot-sector.expected").read_bytes()
        self.assertEqual([i for i in range(512) if before[i] != after[i]], [65])
        self.assertTrue((backup / "complete").exists())
        self.assertEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), clean)

    def test_orphan_cluster_is_not_repaired(self):
        with self.volume.open("rb") as stream:
            boot = stream.read(512)
        reserved = struct.unpack_from("<H", boot, 14)[0]
        sectors = struct.unpack_from("<I", boot, 36)[0]
        for fat in range(boot[16]):
            self.write_at((reserved + fat * sectors) * 512 + 100 * 4,
                          struct.pack("<I", 0x0fffffff))
        self.write_at(65, b"\x01")
        before = self.digest()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), before)

    def test_additional_boot_difference_is_not_repaired(self):
        self.write_at(65, b"\x01")
        self.write_at(3, b"X")
        before = self.digest()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), before)

    def test_other_status_bits_are_not_cleared(self):
        self.write_at(65, b"\x03")
        before = self.digest()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), before)

    def test_stale_fsinfo_count_with_and_without_dirty(self):
        for dirty in (0, 1):
            with self.subTest(dirty=dirty):
                clean = self.volume.read_bytes()
                count = struct.unpack_from("<I", clean, 1000)[0]
                self.write_at(1000, struct.pack("<I", count - 1))
                self.write_at(65, bytes([dirty]))
                result = self.run_check()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.volume.read_bytes(), clean)
                for backup in self.state.iterdir():
                    shutil.rmtree(backup)

    def test_stale_fsinfo_with_orphan_refuses_all_writes(self):
        boot = self.volume.read_bytes()[:512]
        reserved = struct.unpack_from("<H", boot, 14)[0]
        sectors = struct.unpack_from("<I", boot, 36)[0]
        for fat in range(boot[16]):
            self.write_at((reserved + fat * sectors) * 512 + 100 * 4,
                          struct.pack("<I", 0x0fffffff))
        self.write_at(1000, struct.pack("<I", 42))
        self.write_at(65, b"\x01")
        before = self.digest()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), before)

    def test_invalid_fsinfo_signature_is_not_repaired(self):
        self.write_at(512, b"BAD!")
        self.write_at(65, b"\x01")
        before = self.digest()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), before)

    def test_captured_v5d_reboot_dirty_and_stale_count(self):
        capture = ROOT / "out/rgsp-v5d-reboot-failure-20260913/head64.before.bin.gz"
        if not capture.exists():
            self.skipTest("private v5d reboot capture not present")
        self.assertEqual(hashlib.sha256(capture.read_bytes()).hexdigest(),
                         "aad844c1c137ee8a2c01eb837ea9d016521c8dfbf3ce04ce9356cd30b17f92a8")
        with gzip.open(capture, "rb") as stream:
            prefix = stream.read()
        with self.volume.open("wb") as stream:
            stream.write(prefix)
            stream.truncate(struct.unpack_from("<I", prefix, 32)[0] * 512)
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = bytearray(prefix)
        expected[65] = 0
        self.assertEqual(struct.unpack_from("<I", expected, 1000)[0], 2957351)
        struct.pack_into("<I", expected, 1000, 2957350)
        with self.volume.open("rb") as stream:
            self.assertEqual(stream.read(len(prefix)), expected)
        self.assertEqual(self.run_check().returncode, 0)

    def test_wrong_device_argument_refused(self):
        before = self.digest()
        result = subprocess.run(["sh", str(self.script), "/dev/not-the-card",
                                 str(self.state)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(), before)

    @unittest.skipUnless(shutil.which("mcopy"), "mtools required")
    def test_dirty_only_preserves_unicode_file(self):
        name = "\u4e2d\u6587.txt"
        sentinel = self.root / name
        sentinel.write_bytes(b"preserve ROMS content\n" * 64)
        subprocess.run(["mcopy", "-i", str(self.volume), str(sentinel), "::" + name],
                       check=True, capture_output=True,
                       env={**os.environ, "LC_ALL": "C.UTF-8"})
        clean = self.digest()
        self.write_at(65, b"\x01")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.digest(), clean)

    def test_android_block_mount_alias_refused(self):
        mounts = self.root / "mounts"
        mounts.write_text("/dev/block/mmcblk0p8 /rgsp-persist vfat rw 0 0\n")
        self.script.write_text(self.script.read_text().replace("/proc/mounts", str(mounts)))
        self.write_at(65, b"\x01")
        before = self.digest()
        self.assertNotEqual(self.run_check().returncode, 0)
        self.assertEqual(self.digest(), before)

    def test_captured_128gb_card_dirty_case(self):
        capture = ROOT / "out/rgsp-v5c-fat-dirty-20260913/head64.before.bin.gz"
        if not capture.exists():
            self.skipTest("private physical-card prefix not present")
        with gzip.open(capture, "rb") as stream:
            prefix = stream.read()
        self.assertEqual(hashlib.sha256(prefix).hexdigest(),
                         "799e5a5c4b3e002a3210c660f2156e1e885e032505e846ee41ad39a10911ec2f")
        with self.volume.open("wb") as stream:
            stream.write(prefix)
            stream.truncate(struct.unpack_from("<I", prefix, 32)[0] * 512)
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.volume.open("rb") as stream:
            repaired = stream.read(len(prefix))
        self.assertEqual(hashlib.sha256(repaired).hexdigest(),
                         "99c2717e90ab778bc73f198ddd2ee44229aae31b68d0070a55fe2471d1b409e2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
