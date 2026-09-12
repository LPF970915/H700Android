#!/usr/bin/env python3
"""Local-only validation of the FAT repair review gates."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from prepare_rgsp_p1_audio_repair import byte_changes, require_clean


class P1ReviewTests(unittest.TestCase):
    def test_clean_check(self):
        require_clean(subprocess.CompletedProcess([], 0, "574 files, 420694/516190 clusters\n", ""))

    def test_exit_zero_does_not_hide_diagnostics(self):
        for diagnostic in ("Dirty bit is set", "Free cluster summary wrong",
                           "Truncating file", "There are differences",
                           "corrupt", "Filesystem was modified"):
            with self.subTest(diagnostic=diagnostic):
                with self.assertRaises(ValueError):
                    require_clean(subprocess.CompletedProcess([], 0, diagnostic, ""))

    def test_nonzero_check_rejected(self):
        with self.assertRaises(ValueError):
            require_clean(subprocess.CompletedProcess([], 1, "574 files", ""))

    def test_exact_diff_and_unchanged_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after = Path(directory) / "before", Path(directory) / "after"
            before.write_bytes(b"prefix-A-tail")
            after.write_bytes(b"prefix-B-tail")
            self.assertEqual(byte_changes(before, after),
                             [{"offset": 7, "before": 65, "after": 66}])
            self.assertEqual(before.read_bytes(), b"prefix-A-tail")
            self.assertEqual(after.read_bytes(), b"prefix-B-tail")

    def test_size_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after = Path(directory) / "before", Path(directory) / "after"
            before.write_bytes(b"abc")
            after.write_bytes(b"ab")
            with self.assertRaises(ValueError):
                byte_changes(before, after)

    def test_broad_changes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after = Path(directory) / "before", Path(directory) / "after"
            before.write_bytes(b"a" * 4097)
            after.write_bytes(b"b" * 4097)
            with self.assertRaises(ValueError):
                byte_changes(before, after)


if __name__ == "__main__":
    unittest.main()
