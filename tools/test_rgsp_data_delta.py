import copy
import errno
import gzip
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import deploy_rgsp_data_delta as d


class DeltaTest(unittest.TestCase):
    def rows(self):
        return d.manifest((d.BASE / "offline-counter-trial/block-diff.json").read_bytes())

    def test_manifest_pinned(self):
        rows = self.rows()
        self.assertEqual(len(rows), 24)
        with self.assertRaises(ValueError):
            d.manifest(json.dumps(rows).encode())

    def test_manifest_rejects_bad_offsets_counts_and_hashes(self):
        for change in ("duplicate", "unaligned", "negative", "overflow", "short", "hash", "count"):
            rows = copy.deepcopy(self.rows())
            if change == "duplicate":
                rows[1]["offset"] = rows[0]["offset"]
            elif change == "unaligned":
                rows[1]["offset"] += 1
            elif change == "negative":
                rows[0]["offset"] = -4096
            elif change == "overflow":
                rows[-1]["offset"] = d.SIZE
            elif change == "short":
                rows[-1]["bytes"] = 2048
            elif change == "hash":
                rows[-1]["after_sha256"] = "bad"
            else:
                rows.pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.validate_records(rows)

    def exercise(self, failure=None):
        old = b"A" * d.BLOCK + b"B" * d.BLOCK + b"C" * d.BLOCK
        blocks = [(0, old[:d.BLOCK], b"D" * d.BLOCK),
                  (d.BLOCK, old[d.BLOCK:2*d.BLOCK], b"E" * d.BLOCK)]
        logs, calls = [], []
        with tempfile.TemporaryFile() as file:
            file.write(old)
            file.flush()
            fd = file.fileno()
            real_write = os.pwrite
            def write(fd, data, offset):
                calls.append(offset)
                if failure == "short" and len(calls) == 1:
                    return real_write(fd, data[:64], offset)
                if failure == "write_error" and len(calls) == 1:
                    raise OSError("device write failed")
                if failure == "rollback" and len(calls) == 3:
                    raise OSError("rollback failed")
                return real_write(fd, data, offset)
            def verify():
                if failure in ("verify", "rollback", "rollback_hash"):
                    raise ValueError("bad full readback")
            def same():
                if failure == "identity":
                    raise ValueError("identity changed")
            def original():
                if failure == "rollback_hash":
                    raise ValueError("full rollback hash differs")
                self.assertEqual(os.pread(fd, len(old), 0), old)
            real_read = os.pread
            corrupted = False
            def read(fd, length, offset):
                nonlocal corrupted
                if failure == "block_readback" and calls and not corrupted:
                    corrupted = True
                    return b"X" * length
                return real_read(fd, length, offset)
            with patch.object(d.os, "pwrite", side_effect=write), patch.object(d.os, "pread", side_effect=read):
                if failure:
                    with self.assertRaises((ValueError, RuntimeError)):
                        d.apply_blocks(fd, blocks, verify, same, lambda: None,
                                       lambda **v: logs.append(v), original)
                else:
                    d.apply_blocks(fd, blocks, verify, same, lambda: None,
                                   lambda **v: logs.append(v), original)
            if failure not in ("rollback", "rollback_hash"):
                expected = old if failure else b"D" * d.BLOCK + b"E" * d.BLOCK + b"C" * d.BLOCK
                self.assertEqual(os.pread(fd, len(old), 0), expected)
        return calls, logs

    def test_superblock_last_and_no_unrelated_writes(self):
        calls, _ = self.exercise()
        self.assertEqual(calls, [4096, 0])

    def test_short_write_rolls_back_partial_block_no_retry(self):
        calls, logs = self.exercise("short")
        self.assertEqual(calls, [4096, 4096])
        self.assertEqual(logs[-1]["status"], "APPLY_FAILED_ORIGINAL_RESTORED")

    def test_full_readback_failure_rolls_back_superblock_last(self):
        calls, logs = self.exercise("verify")
        self.assertEqual(calls, [4096, 0, 4096, 0])
        self.assertEqual(logs[-1]["status"], "APPLY_FAILED_ORIGINAL_RESTORED")

    def test_block_readback_failure_rolls_back(self):
        _, logs = self.exercise("block_readback")
        self.assertEqual(logs[-1]["status"], "APPLY_FAILED_ORIGINAL_RESTORED")

    def test_write_exception_includes_failed_block_in_rollback(self):
        calls, logs = self.exercise("write_error")
        self.assertEqual(calls, [4096, 4096])
        self.assertEqual(logs[-1]["status"], "APPLY_FAILED_ORIGINAL_RESTORED")

    def test_rollback_failure_explicit(self):
        _, logs = self.exercise("rollback")
        self.assertEqual(logs[-1]["status"], "ROLLBACK_FAILED_DO_NOT_BOOT")

    def test_rollback_full_hash_failure_not_reported_restored(self):
        _, logs = self.exercise("rollback_hash")
        self.assertEqual(logs[-1]["status"], "ROLLBACK_FAILED_DO_NOT_BOOT")

    def test_mismatched_live_preimage_never_writes(self):
        with tempfile.TemporaryFile() as file:
            file.write(b"X" * d.BLOCK)
            file.flush()
            with patch.object(d.os, "pwrite") as write, self.assertRaises(ValueError):
                d.apply_blocks(file.fileno(), [(0, b"A" * d.BLOCK, b"B" * d.BLOCK)],
                               lambda: None, lambda: None, lambda: None,
                               lambda **v: None, lambda: None)
            write.assert_not_called()

    def test_short_hash_read_rejected(self):
        with tempfile.TemporaryFile() as file:
            with self.assertRaises(OSError):
                d.hash_fd(file.fileno(), d.BLOCK, "test", lambda **v: None)

    def test_header_recovery_and_counter_guards(self):
        fields = {"Filesystem UUID": d.UUID, "Filesystem state": "clean",
                  "Free blocks": "4058631", "Free inodes": "1045965",
                  "Block count": "4194304", "Block size": "4096",
                  "Filesystem features": "has_journal extent"}
        text = "\n".join(k + ": " + v for k, v in fields.items())
        d.strict_header(text)
        for bad in (text + " needs_recovery", text.replace("4058631", "4058624"),
                    text.replace(d.UUID, "different"), text + "\nBlock size: 4096"):
            with self.assertRaises(ValueError):
                d.strict_header(bad)

    def test_payload_tampering_rejected(self):
        bundle = d.BASE / "data-approved-delta.json.gz"
        if not bundle.exists():
            self.skipTest("Run the full-image bundle builder first")
        packed = bundle.read_bytes()
        self.assertEqual(len(d.load_bundle(bundle, d.sha(packed))), 24)
        with self.assertRaises(ValueError):
            d.load_bundle(bundle, "0" * 64)
        value = json.loads(gzip.decompress(packed))
        for change in ("length", "content", "manifest", "image"):
            corrupt = copy.deepcopy(value)
            if change == "length":
                corrupt["payload"][0]["before"] = ""
            elif change == "content":
                corrupt["payload"][0]["after"] = corrupt["payload"][0]["before"]
            elif change == "manifest":
                corrupt["manifest"] = ""
            else:
                corrupt["candidate_sha256"] = "0" * 64
            raw = gzip.compress(json.dumps(corrupt).encode())
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "bad.gz"
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    d.load_bundle(path, d.sha(raw))

    def test_identity_failure_does_not_write(self):
        calls, _ = self.exercise("identity")
        self.assertEqual(calls, [])

    def test_zero_exit_with_diagnostics_rejected(self):
        clean = "\n".join(f"Pass {n}: Checking" for n in range(1, 6))
        d.strict_fsck(subprocess.CompletedProcess([], 0, clean, ""))
        for text in (clean + "\nFix? no", clean + "\nFree blocks count wrong",
                     clean + "\nWARNING", "clean"):
            with self.assertRaises(ValueError):
                d.strict_fsck(subprocess.CompletedProcess([], 0, text, ""))

    @unittest.skipUnless(os.geteuid() == 0, "Root loop-device integration test")
    def test_exclusive_mount_exclusion_and_strict_fsck_after_writer_closed(self):
        with tempfile.TemporaryDirectory(prefix="rgsp-delta-test-") as temp:
            path = Path(temp)
            image = path / "loop.img"
            with image.open("xb") as stream:
                stream.truncate(64 * 1024**2)
            subprocess.run(["mke2fs", "-qt", "ext4", "-F", str(image)], check=True, capture_output=True)
            loop = subprocess.check_output(["losetup", "--find", "--show", str(image)], text=True).strip()
            mount = path / "mount"
            mount.mkdir()
            fd = None
            try:
                fd = os.open(loop, os.O_RDWR | os.O_EXCL | os.O_NOFOLLOW)
                d.flush_device(fd)
                fsck = d.run("e2fsck", "-fn", loop)
                self.assertEqual(fsck.returncode, 0, fsck.stdout + fsck.stderr)
                self.assertIn("is in use", fsck.stdout + fsck.stderr)
                with self.assertRaises(ValueError):
                    d.strict_fsck(fsck)
                result = subprocess.run(["mount", "-o", "ro,noload", loop, str(mount)],
                                        capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                with self.assertRaises(OSError) as caught:
                    os.open(loop, os.O_RDWR | os.O_EXCL)
                self.assertEqual(caught.exception.errno, errno.EBUSY)
                os.close(fd)
                fd = None
                d.strict_fsck(d.run("e2fsck", "-fn", loop))
                subprocess.run(["mount", "-o", "ro,noload", loop, str(mount)],
                               check=True, capture_output=True)
                try:
                    with self.assertRaises(OSError):
                        os.open(loop, os.O_RDWR | os.O_EXCL)
                finally:
                    subprocess.run(["umount", str(mount)], check=True, capture_output=True)
            finally:
                if fd is not None:
                    os.close(fd)
                subprocess.run(["losetup", "-d", loop], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
