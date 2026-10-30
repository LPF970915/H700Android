"""Boundary tests for ROM-free release metadata; no image or device mutations."""
import tempfile
import io
import copy
import unittest
from pathlib import Path

import package_h700_v6a as release
import package_h700_v6b as mt_release


class ReleaseGuards(unittest.TestCase):
    def test_reject_absolute_traversal_and_command_paths(self):
        for bad in ('../bad', '/dev/sda', 'a/../b', 'a\\b', 'a\nb', 'a\rb'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                release.relative(bad)

    def test_debugfs_rejects_embedded_command_characters(self):
        for bad in ('x" y', 'x\nwrite bad', 'x\\y'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                release.q(bad)

    def test_vendor_labels_do_not_become_system_labels(self):
        self.assertEqual(release.context_for('vendor', '/etc/init/axes.rc'),
                         b'u:object_r:vendor_configs_file:s0\x00')
        self.assertEqual(release.context_for('vendor', '/modules/axes.ko'),
                         b'u:object_r:vendor_file:s0\x00')

    def test_rom_references_and_case_sensitive_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media/Test'
            media.mkdir(parents=True)
            for name in ('boxFront.png', 'logo.png', 'video.mp4'):
                (media / name).write_bytes(b'owned fixture')
            source = ('collection: GBA\n\ngame: Test\nfiles:\n'
                      '  nested/a.zip\n  b.zip\n'
                      'assets.box_front: media/obsolete/boxfront.png\n')
            text, count = release.adapt_metadata('GBA', source, root)
            self.assertEqual(count, 1)
            self.assertIn('@H700_ROMS_ROOT@/GBA/nested/a.zip', text)
            self.assertIn('@H700_ROMS_ROOT@/GBA/b.zip', text)
            self.assertIn('boxFront.png', text)
            self.assertNotIn('obsolete', text)
            self.assertNotIn('assets.box_front: media/', text)
            with self.assertRaises(ValueError):
                release.adapt_metadata('GBA', 'game: Test\nfile: ../x.zip\n', root)

    def test_media_whitelist_excludes_rom_archives(self):
        self.assertFalse(release.MEDIA & release.ROM)
        self.assertFalse(release.THEME & release.ROM)
        self.assertTrue({'.gba', '.zip', '.7z', '.iso', '.sav'} <= release.ROM)

    def test_mt_is_the_only_authorized_addition(self):
        parent = [{'id': str(i)} for i in range(7)]
        mt = {'id': 'MTManager', 'package': 'bin.mt.plus', 'sha256': mt_release.MT_SHA,
              'bytes': 37521106, 'file': 'out/mt-manager-20261030/MT2.26.10.apk'}
        selected = copy.deepcopy(parent) + [mt]
        mt_release.check_apps(parent, selected)
        for wrong in [selected + [mt], selected[:-1], [{'id': 'changed'}] + selected[1:]]:
            with self.assertRaises(ValueError):
                mt_release.check_apps(parent, wrong)

    def test_range_stream_does_not_silently_truncate(self):
        target = io.BytesIO()
        with self.assertRaises(ValueError):
            mt_release.transfer_exact(io.BytesIO(b'abc'), 4, target.write)
        self.assertEqual(target.getvalue(), b'abc')

    def test_contiguous_image_ranges(self):
        good = [{'offset': 0, 'bytes': 3}, {'offset': 3, 'bytes': 2}]
        self.assertEqual(mt_release.validate_ranges(good), 5)
        for bad in [[{'offset': 0, 'bytes': 0}], [{'offset': 1, 'bytes': 3}],
                    [good[0], {'offset': 2, 'bytes': 2}]]:
            with self.assertRaises(ValueError):
                mt_release.validate_ranges(bad)


if __name__ == '__main__':
    unittest.main()
