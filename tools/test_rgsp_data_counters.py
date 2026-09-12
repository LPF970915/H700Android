import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import json
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_rgsp_data_copy import check_readonly_result, header_fields
from prepare_rgsp_data_counter_copy import counter_fixes, apply_counts, counter_source_inventory


class CounterTest(unittest.TestCase):
    def test_missing_journal_inventory_is_captured_without_altering_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            journal, output = root / "journal", root / "counter"
            journal.mkdir()
            output.mkdir()
            entries = {"app/base.apk": {"sha256": "a" * 64}}
            with patch("prepare_rgsp_data_counter_copy.snapshot", return_value=entries):
                self.assertEqual(counter_source_inventory(root / "image", journal, output), entries)
            self.assertFalse((journal / "files-after.json").exists())
            self.assertEqual(json.loads((output / "files-before-counter.json").read_text()), entries)

    def test_existing_journal_inventory_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            journal, output = root / "journal", root / "counter"
            journal.mkdir()
            output.mkdir()
            (journal / "files-after.json").write_text("{}")
            with patch("prepare_rgsp_data_counter_copy.snapshot", return_value={"new": {}}):
                with self.assertRaises(ValueError):
                    counter_source_inventory(root / "image", journal, output)
            self.assertFalse((output / "files-before-counter.json").exists())

    def test_unknown_diagnostics_cannot_be_accepted_as_counter_only(self):
        text = "\n".join(f"Pass {n}: Checking" for n in range(1, 6))
        text += "\nFree blocks count wrong (100, counted=107).\nFix? no\n"
        text += "\nFree inodes count wrong (10, counted=11).\nFix? no\n"
        result = subprocess.CompletedProcess([], 0, text, "")
        self.assertEqual(counter_fixes(result)["free_blocks_count"]["after"], 107)
        for extra in ("\nInode checksum invalid", "\nClear inode? no", "\nWARNING"):
            with self.assertRaises(ValueError):
                counter_fixes(subprocess.CompletedProcess([], 0, text + extra, ""))

    @unittest.skipUnless(all(shutil.which(c) for c in ("mke2fs", "e2fsck", "debugfs")),
                         "Real e2fsprogs required")
    def test_real_counter_only_correction_and_diagnostics_guard(self):
        env = {**os.environ, "LC_ALL": "C"}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            image = folder / "test.img"
            with image.open("xb") as stream:
                stream.truncate(64 * 1024 * 1024)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", str(image)],
                           check=True, capture_output=True, timeout=30)
            header = subprocess.check_output(["tune2fs", "-l", str(image)], text=True, env=env)
            values = header_fields(header)
            for field, value in (("free_blocks_count", int(values["Free blocks"]) - 7),
                                 ("free_inodes_count", int(values["Free inodes"]) - 1)):
                subprocess.run(["debugfs", "-w", "-R", f"set_super_value {field} {value}",
                                str(image)], check=True, capture_output=True, timeout=10)
            observed = subprocess.run(["e2fsck", "-fn", str(image)], capture_output=True,
                                      text=True, env=env, timeout=30)
            with self.assertRaises(ValueError):
                check_readonly_result(observed)
            fixes = counter_fixes(observed)
            apply_counts(image, fixes, folder)
            result = subprocess.run(["e2fsck", "-fn", str(image)], capture_output=True,
                                    text=True, env=env, timeout=30)
            check_readonly_result(result)


if __name__ == "__main__":
    unittest.main()
