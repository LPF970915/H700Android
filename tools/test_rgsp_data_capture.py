import gzip
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from tools.capture_rgsp_data_readonly import compress, digest, identity, verify_archive


class DataCaptureTest(unittest.TestCase):
    def test_identity_rejects_wrong_card_power_guid_and_mount_state(self):
        readings = {
            "/sys/block/mmcblk0/device/cid": "1d414455534400002000009f9401a1e7",
            "/sys/block/mmcblk1/device/cid": "fe3432534400000020000005bc01896b",
            "/sys/class/power_supply/axp2202-usb/online": "1",
            "/proc/sys/kernel/random/boot_id": "boot-id",
        }
        def remote(*args):
            if args[0] == "findmnt":
                return "/dev/mmcblk0p5"
            if args[0] == "blockdev":
                return "17179869184"
            return {"PARTUUID": "734716ed-e7d9-e74f-9b3e-4f1cb8d448ed",
                    "UUID": "45daaa6e-724e-4d20-981c-602b3f72b8a2", "TYPE": "ext4"}[args[2]]
        with patch("tools.capture_rgsp_data_readonly.os.geteuid", return_value=0), \
                patch("tools.capture_rgsp_data_readonly.command", side_effect=remote) as run, \
                patch.object(Path, "read_text", lambda path: readings[str(path)]), \
                patch.object(Path, "exists", return_value=False) as exists, \
                patch("tools.capture_rgsp_data_readonly.subprocess.run") as mount:
            mount.return_value = subprocess.CompletedProcess([], 1)
            self.assertEqual(identity()["boot_id"], "boot-id")
            for path in ("/sys/block/mmcblk1/device/cid",
                         "/sys/class/power_supply/axp2202-usb/online"):
                old = readings[path]
                readings[path] = "wrong"
                with self.assertRaises(ValueError):
                    identity()
                readings[path] = old
            for rc in (0, 2):
                mount.return_value = subprocess.CompletedProcess([], rc)
                with self.assertRaises(ValueError):
                    identity()
            mount.return_value = subprocess.CompletedProcess([], 1)
            exists.return_value = True
            with self.assertRaises(ValueError):
                identity()
            exists.return_value = False
            run.side_effect = lambda *args: "wrong" if args[0] == "blkid" else remote(*args)
            with self.assertRaises(ValueError):
                identity()

    def test_complete_stream_includes_zero_and_nonzero_bytes(self):
        content = bytes(range(256)) * 1024 + bytes(1024 * 1024) + b"tail"
        result = io.BytesIO()
        sha = compress(io.BytesIO(content), result, len(content))
        self.assertEqual(gzip.decompress(result.getvalue()), content)
        self.assertEqual(sha, hashlib.sha256(content).hexdigest())

    def test_truncated_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EOF"):
            compress(io.BytesIO(b"short"), io.BytesIO(), 10)
        with self.assertRaisesRegex(ValueError, "EOF"):
            digest(io.BytesIO(b"short"), 10)

    def test_archive_size_hash_and_crc_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.gz"
            content = b"test content" * 100
            sha = hashlib.sha256(content).hexdigest()
            path.write_bytes(gzip.compress(content))
            self.assertEqual(verify_archive(path, len(content), sha), sha)
            with self.assertRaises(ValueError):
                verify_archive(path, len(content) - 1, sha)
            with self.assertRaises(ValueError):
                verify_archive(path, len(content) + 1, sha)
            with self.assertRaisesRegex(ValueError, "hash"):
                verify_archive(path, len(content), "0" * 64)
            path.write_bytes(path.read_bytes()[:-4])
            with self.assertRaises(EOFError):
                verify_archive(path, len(content), sha)


if __name__ == "__main__":
    unittest.main()
