"""Recovery integration tests use the real frozen overlay and temporary trees."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import restore_h700_baseline as recovery


class RecoveryTest(unittest.TestCase):
    def test_frozen_payloads_match_lock(self):
        self.assertGreater(len(recovery.verify_snapshot()), 99)

    def test_plan_apply_backup_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'android'
            (source / 'build').mkdir(parents=True)
            (source / 'build/envsetup.sh').write_text('# fixture\n')
            relative = 'system/core/adb/daemon/main.cpp'
            original = source / relative
            original.parent.mkdir(parents=True)
            original.write_text('fixture original\n')
            planned = recovery.restore(source)
            self.assertGreater(planned['changed_files'], 99)
            self.assertEqual(original.read_text(), 'fixture original\n')
            applied = recovery.restore(source, root / 'backup', True)
            self.assertEqual(applied['changed_files'], planned['changed_files'])
            self.assertEqual((root / 'backup' / relative).read_text(), 'fixture original\n')
            self.assertEqual(recovery.restore(source)['changed_files'], 0)
            journal = json.loads((root / 'backup/restore-journal.json').read_text())
            self.assertTrue(any(x['path'] == relative and x['existed'] for x in journal))

    def test_apply_requires_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'build').mkdir()
            (source / 'build/envsetup.sh').write_text('')
            with self.assertRaisesRegex(ValueError, 'requires'):
                recovery.restore(source, apply=True)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                recovery.safe_path(root, '../outside')

    def test_tampered_frozen_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'payload.java').write_text('changed')
            lock = root / 'lock.json'
            lock.write_text(json.dumps({'files': {'file.java': {
                'repository_path': 'payload.java', 'bytes': 8,
                'sha256': hashlib.sha256(b'original').hexdigest()}}}))
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                recovery.verify_snapshot(root, lock)


if __name__ == '__main__':
    unittest.main()
