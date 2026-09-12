import gzip
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from analyze_rgsp_data_copy import (REPLAY_ARGS, check_replay_result,
                                    block_changes, expand_verified, header_fields,
                                    regular, sha, snapshot, check_readonly_result)


class DataCopyTest(unittest.TestCase):
    def test_copy_is_exact_including_trailing_zeroes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = b"abc" + bytes(2 * 1024 * 1024)
            archive, copy = root / "archive.gz", root / "copy.img"
            archive.write_bytes(gzip.compress(content))
            expand_verified(archive, copy, len(content), hashlib.sha256(content).hexdigest())
            self.assertEqual(copy.read_bytes(), content)
            with self.assertRaises(FileExistsError):
                expand_verified(archive, copy, len(content), hashlib.sha256(content).hexdigest())

    def test_copy_rejects_wrong_hash_and_oversized_stream(self):
        for size in (2, 3):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / "archive.gz"
                archive.write_bytes(gzip.compress(b"abc"))
                with self.assertRaises(ValueError):
                    expand_verified(archive, root / "copy.img", size, "0" * 64)

    def test_symlink_and_hardlink_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "file"
            image.write_bytes(b"data")
            alias = root / "alias"
            alias.symlink_to(image)
            with self.assertRaises(ValueError):
                regular(alias)
            alias.unlink()
            alias.hardlink_to(image)
            with self.assertRaises(ValueError):
                regular(image)

    def test_full_check_or_failure_is_not_journal_only_success(self):
        for rc, text in ((4, ""), (0, "Pass 1: Checking inodes")):
            with self.subTest(rc=rc):
                result = subprocess.CompletedProcess([], rc, text, "")
                with self.assertRaises(ValueError):
                    check_replay_result(result)
        check_replay_result(subprocess.CompletedProcess([], 1, "recovering journal", ""))

    def test_zero_exit_does_not_hide_counter_diagnostics(self):
        clean = "\n".join(f"Pass {n}: Checking" for n in range(1, 6))
        check_readonly_result(subprocess.CompletedProcess([], 0, clean, ""))
        for output in ("", clean + "\nFree blocks count wrong (12, counted=13).\nFix? no"):
            with self.assertRaises(ValueError):
                check_readonly_result(subprocess.CompletedProcess([], 0, output, ""))

    def test_headers_require_known_unique_fields(self):
        with self.assertRaises(ValueError):
            header_fields("Filesystem state: clean")
        with self.assertRaises(ValueError):
            header_fields("Filesystem state: clean\nFilesystem state: clean")
        values = header_fields("Filesystem UUID: a\nFilesystem features: needs_recovery\nFilesystem state: clean")
        self.assertIn("needs_recovery", values["Filesystem features"])

    def test_block_diff_reports_exact_offsets_without_changing_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, candidate = root / "before.gz", root / "after.img"
            before = bytes(8192)
            after = bytearray(before)
            after[4100] = 1
            archive.write_bytes(gzip.compress(before))
            candidate.write_bytes(after)
            original_hash = sha(archive)
            with patch("analyze_rgsp_data_copy.DATA_BYTES", 8192):
                delta = block_changes(archive, candidate)
            self.assertEqual([row["offset"] for row in delta], [4096])
            self.assertEqual(sha(archive), original_hash)

    @unittest.skipUnless(os.geteuid() == 0 and shutil.which("mke2fs"),
                         "Root loop mount support required")
    def test_inventory_mount_does_not_replay_or_modify_real_image(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "copy.img"
            size = 64 * 1024 * 1024
            with image.open("xb") as stream:
                stream.truncate(size)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", str(image)],
                           check=True, capture_output=True, timeout=30)
            subprocess.run(["debugfs", "-w", "-R", "feature needs_recovery", str(image)],
                           check=True, capture_output=True, timeout=10)
            before = sha(image)
            with patch("analyze_rgsp_data_copy.DATA_BYTES", size):
                entries = snapshot(image)
            self.assertIn("lost+found", entries)
            self.assertEqual(sha(image), before)

    @unittest.skipUnless(shutil.which("mke2fs") and shutil.which("e2fsck"),
                         "Real e2fsprogs required")
    def test_exact_replay_arguments_skip_full_passes_on_real_copy(self):
        self.assertEqual(REPLAY_ARGS, ["e2fsck", "-E", "journal_only", "-y"])
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "copy.img"
            with image.open("xb") as stream:
                stream.truncate(64 * 1024 * 1024)
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-F", str(image)],
                           check=True, capture_output=True, timeout=30)
            result = subprocess.run(REPLAY_ARGS + [str(image)], text=True,
                                    capture_output=True, timeout=30)
            check_replay_result(result)


if __name__ == "__main__":
    unittest.main()
