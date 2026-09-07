#!/usr/bin/env python3
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compare_rgsp_image_files import inventory
from prepare_rgsp_wifi_deployment import main, props, sha


class DeploymentHelpersTest(unittest.TestCase):
    def test_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "file"
            path.write_bytes(b"abc")
            self.assertEqual(sha(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_properties_replace_exact_keys_and_remove_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "build.prop"
            path.write_text("# retained\np.x=old\np.x=duplicate\np.xy=keep\n")
            props(path, {"p.x": "new"})
            self.assertEqual(path.read_text(), "# retained\np.xy=keep\np.x=new\n")

    def test_inventory_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "file").write_bytes(b"abc")
            os.symlink("/does/not/exist", root / "link")
            result = inventory(root)
            self.assertEqual(result["link"]["symlink"], "/does/not/exist")
            self.assertIn("sha256", result["file"])
            json.dumps(result)

    def test_output_gate_precedes_any_mount_or_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            outside = Path(temp) / "outside"
            for output in (outside, root / "out", root):
                with patch("sys.argv", ["prepare", "--workspace", str(root), "--output", str(output)]):
                    with self.assertRaises(ValueError):
                        main()
            self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
