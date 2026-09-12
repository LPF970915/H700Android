"""Host-only safety tests for the narrow, local codec image packager."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from prepare_rgsp_codec_candidate import (
    XML_HASHES, check_delta, check_filesystem, new_output, verify_image,
)


class CodecCandidateTest(unittest.TestCase):
    def setUp(self):
        self.before = {"etc": {"directory": True}, "lib/gpu.so": {"sha256": "frozen"}}
        self.payload = {f"etc/{name}": {"sha256": sha, "mode": 0o644, "uid": 0,
                                      "gid": 0, "xattrs": {"security.selinux": "label"}}
                        for name, sha in XML_HASHES.items()}
        self.after = {**self.before, **copy.deepcopy(self.payload)}

    def test_only_three_files_accepted(self):
        self.assertEqual(len(check_delta(self.before, self.after, self.payload)), 3)

    def test_existing_component_change_rejected(self):
        self.after["lib/gpu.so"] = {"sha256": "new-build"}
        with self.assertRaises(ValueError):
            check_delta(self.before, self.after, self.payload)

    def test_existing_file_removal_rejected(self):
        del self.after["lib/gpu.so"]
        with self.assertRaises(ValueError):
            check_delta(self.before, self.after, self.payload)

    def test_missing_xml_rejected(self):
        del self.after["etc/media_codecs.xml"]
        with self.assertRaises(ValueError):
            check_delta(self.before, self.after, self.payload)

    def test_payload_xattr_change_rejected(self):
        self.after["etc/media_codecs.xml"]["xattrs"] = {}
        with self.assertRaises(ValueError):
            check_delta(self.before, self.after, self.payload)

    def test_payload_owner_change_rejected(self):
        self.after["etc/media_codecs.xml"]["uid"] = 1000
        with self.assertRaises(ValueError):
            check_delta(self.before, self.after, self.payload)

    def test_existing_catalog_rejected(self):
        self.before["etc/media_codecs.xml"] = {"sha256": "old"}
        with self.assertRaises(ValueError):
            check_delta(self.before, self.after, self.payload)

    def test_output_boundary_and_existing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "out").mkdir()
            expected = root / "out/new"
            self.assertEqual(new_output(root, expected), expected)
            for invalid in (root / "outside", root / "out", root / "out/../outside"):
                with self.assertRaises(ValueError):
                    new_output(root, invalid)
            expected.mkdir()
            with self.assertRaises(ValueError):
                new_output(root, expected)

    def test_output_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "out").mkdir()
            (root / "elsewhere").mkdir()
            (root / "out/link").symlink_to(root / "elsewhere", target_is_directory=True)
            with self.assertRaises(ValueError):
                new_output(root, root / "out/link/new")

    def test_directory_and_small_image_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                verify_image(root, "unused")
            image = root / "vendor.img"
            image.write_bytes(b"invalid")
            with self.assertRaises(ValueError):
                verify_image(image, "unused")

    def test_fsck_failure_retains_both_streams_without_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "fsck.txt"
            result = subprocess.CompletedProcess([], 4, "filesystem error\n", "fsck version\n")
            with patch("prepare_rgsp_codec_candidate.subprocess.run", return_value=result) as run:
                with self.assertRaises(ValueError):
                    check_filesystem(Path(temp) / "local.img", report)
            self.assertEqual(report.read_text(), "filesystem error\nfsck version\n")
            self.assertEqual(run.call_args.args[0][:2], ["e2fsck", "-fn"])


if __name__ == "__main__":
    unittest.main()
