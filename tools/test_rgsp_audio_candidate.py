import copy
from pathlib import Path
import tempfile
import unittest

from prepare_rgsp_audio_candidate import FILES, validate_changes, validate_route


class AudioCandidateTests(unittest.TestCase):
    def test_source_route(self):
        validate_route(Path(__file__).resolve().parents[1] /
                       "android/h700-android10/device/roc/rgsp/configs/audio_mixer_paths.xml")

    def test_donor_route_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "route.xml"
            path.write_text('<mixer><ctl name="Speaker Switch" value="1"/></mixer>')
            with self.assertRaises(ValueError):
                validate_route(path)

    def fixture(self):
        before = {p: {"sha256": "old", "mode": 420, "uid": 0, "gid": 0,
                      "xattrs": {"security.selinux": "label"}} for p in FILES}
        before["codec.xml"] = {"sha256": "protected"}
        hashes = {p: "new" for p in FILES}
        after = copy.deepcopy(before)
        for p in FILES:
            after[p]["sha256"] = hashes[p]
        return before, after, hashes

    def test_exact_delta(self):
        self.assertEqual(len(validate_changes(*self.fixture())), 3)

    def test_unrelated_change_rejected(self):
        before, after, hashes = self.fixture()
        after["codec.xml"]["sha256"] = "wrong"
        with self.assertRaises(ValueError):
            validate_changes(before, after, hashes)

    def test_permissions_change_rejected(self):
        before, after, hashes = self.fixture()
        after["ueventd.rc"]["mode"] = 511
        with self.assertRaises(ValueError):
            validate_changes(before, after, hashes)

    def test_label_change_rejected(self):
        before, after, hashes = self.fixture()
        after["ueventd.rc"]["xattrs"] = {}
        with self.assertRaises(ValueError):
            validate_changes(before, after, hashes)

    def test_missing_payload_rejected(self):
        before, after, hashes = self.fixture()
        after["ueventd.rc"] = before["ueventd.rc"]
        with self.assertRaises(ValueError):
            validate_changes(before, after, hashes)


if __name__ == "__main__":
    unittest.main()
