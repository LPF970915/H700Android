"""Offline tests only: sparse regular files, never physical cards."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib
from build_rgsp_compact_image import default_baseline

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path("/home/lpf/rgsp-grow-build")
RUNTIME = Path("/home/lpf/rgsp-grow-runtime/runtime")
START = 28139585536
SEED_SIZE = 4 * 1024**3
MIN_SIZE = START + SEED_SIZE + 1536


def make_gpt(size):
    with default_baseline().open("rb") as f:
        head = bytearray(f.read(2048))
    entries = bytearray(head[1024:])
    struct.pack_into("<Q", entries, 7 * 128 + 40, size // 512 - 4)
    h = bytearray(head[512:1024])
    def header(here, other, array):
        result = bytearray(h)
        struct.pack_into("<QQQQ", result, 24, here, other, 4, size // 512 - 4)
        struct.pack_into("<QIII", result, 72, array, 8, 128, zlib.crc32(entries))
        struct.pack_into("<I", result, 16, 0)
        struct.pack_into("<I", result, 16, zlib.crc32(result[:92]))
        return result
    head[512:1024] = header(1, size // 512 - 1, 2)
    head[1024:] = entries
    struct.pack_into("<I", head, 458, size // 512 - 1)
    return head, entries + header(size // 512 - 1, 1, size // 512 - 3)


def arm_fatresize(path, *args):
    lib = RUNTIME / "usr/lib/aarch64-linux-gnu"
    result = subprocess.run(["qemu-aarch64", str(lib / "ld-linux-aarch64.so.1"),
        "--library-path", str(lib), str(BUILD / "rgsp-grow-fat"),
        *args, str(path)], capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(f"fatresize exit {result.returncode}: {result.stdout}\n{result.stderr}")
    return result


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rgsp-capacity-", dir=BUILD)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.img"

    def seed(self, size):
        head, tail = make_gpt(MIN_SIZE)
        with self.path.open("wb") as f:
            f.truncate(size)
            f.write(head)
            f.seek(8192)
            f.write(b"PROTECTED_BOOT0")
            f.seek(MIN_SIZE - 1536)
            f.write(tail)
        return head

    def normalize_bootloader_gpt(self, size):
        total = size // 512
        with self.path.open("r+b") as f:
            f.seek(512)
            primary = bytearray(f.read(512))
            struct.pack_into("<Q", primary, 32, total - 1)
            struct.pack_into("<Q", primary, 48, total - 4)
            struct.pack_into("<I", primary, 16, 0)
            struct.pack_into("<I", primary, 16, zlib.crc32(primary[:92]))
            f.seek(512)
            f.write(primary)
            f.seek(1024)
            entries = f.read(1024)
            backup = bytearray(primary)
            struct.pack_into("<Q", backup, 24, total - 1)
            struct.pack_into("<Q", backup, 32, 1)
            struct.pack_into("<Q", backup, 72, total - 3)
            struct.pack_into("<I", backup, 16, 0)
            struct.pack_into("<I", backup, 16, zlib.crc32(backup[:92]))
            f.seek(total * 512 - 3 * 512)
            f.write(entries)
            f.seek(total * 512 - 512)
            f.write(backup)

    def run_helper(self, apply=True, arm=False, expect=0):
        command = (["qemu-aarch64", str(BUILD / "rgsp-grow-gpt")] if arm
                   else [str(BUILD / "grow-host")])
        result = subprocess.run(command + ["--apply" if apply else "--check",
            str(self.path), "--image-test"], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, expect, result.stderr.decode())
        return result

    def test_all_capacities_and_idempotence(self):
        for size in [62239277056, 125069950976, 256_000_000_000,
                     512_000_000_000, 1_000_000_000_000]:
            with self.subTest(size=size):
                old = self.seed(size)
                self.run_helper(arm=True)
                self.run_helper(apply=False)
                with self.path.open("rb") as f:
                    new = f.read(2048)
                    f.seek(8192)
                    self.assertEqual(f.read(15), b"PROTECTED_BOOT0")
                    f.seek(size - 1536)
                    tail = f.read()
                self.assertEqual(new[1024:1920], old[1024:1920])
                self.assertEqual(new[1920:1960], old[1920:1960])
                self.assertEqual(struct.unpack_from("<Q", new, 1960)[0], size // 512 - 4)
                self.run_helper()
                with self.path.open("rb") as f:
                    self.assertEqual(f.read(2048), new)
                    f.seek(size - 1536)
                    self.assertEqual(f.read(), tail)

    def test_undersized_no_write(self):
        self.seed(MIN_SIZE - 512)
        with self.path.open("r+b") as f:
            f.truncate(MIN_SIZE - 512)
        before = self.path.stat().st_size
        self.run_helper(expect=1)
        self.assertEqual(self.path.stat().st_size, before)

    def test_corrupt_entries_no_write(self):
        self.seed(125069950976)
        with self.path.open("r+b") as f:
            f.seek(1030)
            f.write(b"!")
        self.run_helper(expect=1)

    def test_recover_torn_primary(self):
        self.seed(125069950976)
        self.run_helper()
        with self.path.open("r+b") as f:
            f.seek(528)
            f.write(b"\0" * 4)
        self.run_helper()
        self.run_helper(apply=False)

    def test_recover_torn_primary_table(self):
        self.seed(125069950976)
        self.run_helper()
        with self.path.open("r+b") as f:
            f.seek(1960)
            f.write(b"\0" * 8)
        self.run_helper()
        self.run_helper(apply=False)

    def test_accepts_bootloader_normalized_header_before_p8_growth(self):
        size = 125069950976
        self.seed(size)
        self.normalize_bootloader_gpt(size)
        result = self.run_helper(apply=False)
        self.assertIn(b"OLD_END=63348735", result.stdout)
        self.run_helper()
        self.run_helper(apply=False)

    def test_fat_growth_preserves_files(self):
        sizes = [125069950976 - START - 1536, 1_000_000_000_000 - START - 1536]
        for size in sizes:
            with self.subTest(size=size):
                with self.path.open("wb") as f:
                    f.truncate(SEED_SIZE)
                subprocess.run(["mkfs.fat", "-F", "32", "-s", "64", "-n", "ROMS",
                                str(self.path)], check=True, capture_output=True)
                sentinel = Path(self.tmp.name) / "KEEP.TXT"
                sentinel.write_bytes(b"RGSP keep files during expansion\n" * 4096)
                subprocess.run(["mcopy", "-i", str(self.path), str(sentinel), "::KEEP.TXT"],
                               check=True, capture_output=True)
                with self.path.open("r+b") as f:
                    f.truncate(size)
                result = arm_fatresize(self.path)
                print(result.stdout, flush=True)
                lib = RUNTIME / "usr/lib/aarch64-linux-gnu"
                subprocess.run(["qemu-aarch64", str(lib / "ld-linux-aarch64.so.1"),
                    "--library-path", str(lib), str(RUNTIME / "usr/sbin/fatlabel"),
                    str(self.path), "ROMS"], check=True, capture_output=True)
                checked = subprocess.run(["fsck.fat", "-n", str(self.path)],
                                         capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                copied = subprocess.run(["mtype", "-i", str(self.path), "::KEEP.TXT"],
                                        check=True, capture_output=True).stdout
                self.assertEqual(copied, sentinel.read_bytes())
                with self.path.open("rb") as f:
                    boot = f.read(512)
                sectors = struct.unpack_from("<I", boot, 32)[0]
                self.assertLess(size - sectors * 512, 1024**2)
                repeated = arm_fatresize(self.path)
                self.assertIn("FAT_ALREADY_FULL", repeated.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
