import copy
import unittest
from unittest.mock import patch

import collect_rgsp_data_delta_receipt as c
import deploy_rgsp_data_delta as d


class ReceiptTest(unittest.TestCase):
    def fixture(self):
        records = [{"status": "AUTHORIZED_APPLY_START", "script_sha256": "script",
                    "bundle_sha256": "bundle", "authorization_sha256": "auth", "blocks": 24,
                    "protected": {"/dev/mmcblk0p4": d.BOOT, "/dev/mmcblk0p3": d.ENV}}]
        records.extend({"phase": "full_original_hash", "bytes": n, "total": d.SIZE}
                       for n in range(256 * 1024**2, d.SIZE + 1, 256 * 1024**2))
        records.append({"phase": "full_original_verified", "sha256": d.ORIGINAL})
        rows = d.manifest((d.BASE / "offline-counter-trial/block-diff.json").read_bytes())
        ordered = sorted(rows, key=lambda r: (r["offset"] == 0, r["offset"]))
        records.extend({"phase": "block_written", "count": i, "offset": row["offset"]}
                       for i, row in enumerate(ordered, 1))
        records.extend({"phase": "full_candidate_readback", "bytes": n, "total": d.SIZE}
                       for n in range(256 * 1024**2, d.SIZE + 1, 256 * 1024**2))
        records.append({"phase": "full_candidate_verified", "sha256": d.CANDIDATE})
        records.append({"phase": "readonly_fsck", "exit_code": 0,
                        "output": "\n".join(f"Pass {n}: Checking" for n in range(1, 6))})
        records.append({"status": "PHYSICAL_P4_RECOVERY_VERIFIED", "sha256": d.CANDIDATE,
                        "bytes": d.SIZE, "strict_readonly_fsck_clean": True,
                        "boot_marker": False, "data_unmounted": True,
                        "modified_partition": d.DATA, "written_blocks": 24,
                        "protected": records[0]["protected"]})
        return records

    def markers(self):
        return "__CODEX_SERIAL_BEGIN_" + "a" * 32 + "__\n__CODEX_SERIAL_END_" + "a" * 32 + "__:0"

    def validate(self, records):
        return c.validate(self.markers(), records, "script", "bundle", "auth")

    def test_complete_evidence_accepted(self):
        self.assertEqual(self.validate(self.fixture())["sha256"], d.CANDIDATE)

    def test_missing_or_failed_shell_completion_rejected(self):
        for text in ("", self.markers().replace("__:0", "__:1")):
            with self.assertRaises(ValueError):
                c.validate(text, self.fixture(), "script", "bundle", "auth")

    def test_partial_evidence_never_accepted(self):
        records = self.fixture()
        for position in (0, 1, 64, 65, 66, len(records) - 3, len(records) - 2, len(records) - 1):
            with self.subTest(position=position), self.assertRaises((ValueError, KeyError)):
                self.validate(records[:position] + records[position + 1:])

    def test_wrong_scope_or_hash_rejected(self):
        for field, value in (("modified_partition", "/dev/mmcblk1"),
                             ("sha256", d.ORIGINAL), ("boot_marker", True),
                             ("strict_readonly_fsck_clean", False)):
            records = self.fixture()
            records[-1][field] = value
            with self.assertRaises(ValueError):
                self.validate(records)

    def test_wrong_execution_or_authorization_rejected(self):
        for field in ("script_sha256", "bundle_sha256", "authorization_sha256"):
            records = self.fixture()
            records[0][field] = "different"
            with self.assertRaises(ValueError):
                self.validate(records)

    def test_failure_and_fsck_diagnostics_rejected(self):
        records = self.fixture()
        records[-2]["output"] += "\nFree blocks count wrong\nFix? no"
        with self.assertRaises(ValueError):
            self.validate(records)
        records = self.fixture()
        records.insert(1, {"status": "APPLY_FAILED_ORIGINAL_RESTORED"})
        with self.assertRaises(ValueError):
            self.validate(records)

    def test_reordered_writes_rejected(self):
        records = copy.deepcopy(self.fixture())
        records[66], records[67] = records[67], records[66]
        with self.assertRaises(ValueError):
            self.validate(records)

    def test_audio_vendor_preflight_progress_is_exact_and_profile_bound(self):
        records = self.fixture()
        for event in (records[0], records[-1]):
            event["recovery_profile_sha256"] = "profile"
            event["protected"]["/dev/mmcblk1p3"] = "vendor"
        prefix = [{"phase": "protected_hash", "bytes": n, "total": 2147483648}
                  for n in range(256 * 1024**2, 2147483648 + 1, 256 * 1024**2)]
        with patch.object(d, "PROFILE_SHA", "profile"), \
                patch.object(d, "EXTRA_PROTECTED", (("/dev/mmcblk1p3", 2147483648, "vendor"),)):
            self.validate(prefix + records)
            with self.assertRaises(ValueError):
                self.validate(prefix[:-1] + records)
            bad = copy.deepcopy(records)
            bad[-1]["recovery_profile_sha256"] = "different"
            with self.assertRaises(ValueError):
                self.validate(prefix + bad)
        with self.assertRaises(ValueError):
            self.validate(prefix + self.fixture())


if __name__ == "__main__":
    unittest.main()
