import copy
import json
from pathlib import Path
import tempfile
import unittest

import deploy_rgsp_data_delta as d


class AudioProfileTests(unittest.TestCase):
    def setUp(self):
        names = ("BASE ORIGINAL CANDIDATE ARCHIVE MANIFEST BLOCK_COUNT ARCHIVE_BYTES "
                 "TRIAL CANDIDATE_FILE QUALIFIED_STATUS FREE_BLOCKS FREE_INODES "
                 "BUNDLE_LIMIT PROFILE_SHA EXTRA_PROTECTED").split()
        self.saved = {name: getattr(d, name) for name in names}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "profile.json"
        self.value = {
            "schema": "rgsp-audio-data-recovery-v1", "bytes": d.SIZE,
            "original_sha256": "1" * 64, "candidate_sha256": "2" * 64,
            "archive_sha256": "3" * 64, "manifest_sha256": "4" * 64,
            "blocks": 2, "archive_bytes": 1000, "free_blocks": 4000000,
            "free_inodes": 1000000, "trial": "offline-journal-trial",
            "audio_vendor_sha256": "9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2",
        }

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(d, name, value)

    def load(self, value=None, hash_override=None):
        raw = json.dumps(value or self.value).encode()
        self.path.write_bytes(raw)
        d.configure_audio_profile(self.path, hash_override or d.sha(raw))

    def test_legacy_defaults_unchanged_without_explicit_profile(self):
        self.assertEqual(d.BLOCK_COUNT, 24)
        self.assertEqual(d.EXTRA_PROTECTED, ())
        self.assertIsNone(d.PROFILE_SHA)

    def test_exact_profile_selects_current_paths_and_audio_protection(self):
        self.load()
        self.assertEqual(d.BLOCK_COUNT, 2)
        self.assertEqual(d.CANDIDATE_FILE, "data.journal-replayed.img")
        self.assertEqual(d.BASE.name, "tf2-data-backup-audio-20260910")
        self.assertEqual(d.EXTRA_PROTECTED[0][0], "/dev/mmcblk1p3")
        self.assertEqual(d.FREE_BLOCKS, "4000000")

    def test_wrong_profile_hash_rejected_without_reconfiguration(self):
        with self.assertRaises(ValueError):
            self.load(hash_override="0" * 64)
        self.assertEqual(d.BLOCK_COUNT, 24)

    def test_bad_count_bounds_paths_or_vendor_rejected(self):
        for key, bad in (("blocks", 0), ("blocks", 8193), ("blocks", True),
                         ("archive_bytes", -1), ("free_inodes", 1048577),
                         ("trial", "../outside"), ("audio_vendor_sha256", "0" * 64)):
            with self.subTest(key=key, bad=bad):
                value = copy.deepcopy(self.value)
                value[key] = bad
                with self.assertRaises(ValueError):
                    self.load(value)
                self.assertEqual(d.BLOCK_COUNT, 24)

    def test_explicit_count_does_not_relax_offset_or_preimage_rules(self):
        self.load()
        rows = [{"offset": i * d.BLOCK, "bytes": d.BLOCK,
                 "before_sha256": "5" * 64, "after_sha256": "6" * 64} for i in range(2)]
        d.validate_records(rows)
        for field, bad in (("offset", 1), ("bytes", 1), ("after_sha256", "5" * 64)):
            value = copy.deepcopy(rows)
            value[1][field] = bad
            with self.assertRaises(ValueError):
                d.validate_records(value)

    def test_new_header_counts_and_recovery_flag_are_enforced(self):
        self.load()
        text = "\n".join((
            "Filesystem UUID: " + d.UUID, "Filesystem state: clean",
            "Free blocks: 4000000", "Free inodes: 1000000",
            "Block count: 4194304", "Block size: 4096", "Filesystem features: has_journal"))
        d.strict_header(text)
        with self.assertRaises(ValueError):
            d.strict_header(text + " needs_recovery")
        with self.assertRaises(ValueError):
            d.strict_header(text.replace("4000000", "4058631"))


if __name__ == "__main__":
    unittest.main()
