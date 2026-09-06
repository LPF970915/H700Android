import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ramdisk", ROOT / "tools" / "replace_ramdisk_init.py"
)
ramdisk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ramdisk)


def entry(name, data, mode=0o100755):
    name_bytes = name.encode() + b"\0"
    fields = [1, mode, 0, 0, 1, 123, len(data), 0, 0, 0, 0, len(name_bytes), 0]
    result = b"070701" + b"".join(f"{value:08x}".encode() for value in fields)
    result += name_bytes
    result += b"\0" * (ramdisk.align4(len(result)) - len(result))
    result += data
    return result + b"\0" * (ramdisk.align4(len(result)) - len(result))


class ReplaceInitTests(unittest.TestCase):
    def test_alignment_and_non_init_entries_are_preserved(self):
        before = entry("bin", b"", 0o40755) + entry("bin/busybox", b"ELF-data")
        after = entry("lib/loader", b"loader-bytes") + entry("TRAILER!!!", b"", 0)
        source = before + entry("init", b"old init") + after
        for size in (0, 1, 2, 3, 4, 127, 128, 4097):
            with self.subTest(size=size):
                new_init = b"x" * size
                self.assertEqual(
                    ramdisk.replace_entry(source, new_init),
                    before + entry("init", new_init) + after,
                )

    def test_init_metadata_is_preserved(self):
        source = entry("init", b"old", 0o100700) + entry("TRAILER!!!", b"", 0)
        replaced = ramdisk.replace_entry(source, b"#!/bin/sh\n")
        self.assertEqual(replaced[14:22], b"000081c0")
        self.assertEqual(replaced[46:54], b"0000007b")

    def test_invalid_magic_is_rejected(self):
        with self.assertRaises(ValueError):
            ramdisk.replace_entry(b"badmagic" + b"\0" * 110, b"new")


if __name__ == "__main__":
    unittest.main()
