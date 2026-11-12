"""Exercise validation, copy dependencies, and regular-file image assembly."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import extract
import pack
import prepare


class PublicBuildTests(unittest.TestCase):
    def test_path_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'root'
            root.mkdir()
            (root / 'escape').symlink_to(Path(t), target_is_directory=True)
            for name in ['../file', '/file', 'escape/file', 'a\\b', 'a\nb']:
                with self.assertRaises(ValueError):
                    common.inside(root, name)

    def test_wrong_reference_image_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as t:
            image = Path(t) / 'bad.img.gz'
            image.write_bytes(b'incorrect input')
            output = Path(t) / 'output'
            with self.assertRaises(ValueError):
                extract.extract(image, output)
            self.assertFalse(output.exists())

    def test_regular_file_only(self):
        with self.assertRaises(ValueError):
            common.regular('/dev/null')

    def test_assembly_readback_and_overlap(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            a, b = root / 'a', root / 'b'
            a.write_bytes(b'header')
            b.write_bytes(b'payload')
            output = root / 'assembled'
            pack.assemble(output, 4096, [(0, a), (1024, b)])
            self.assertEqual(output.stat().st_size, 4096)
            self.assertEqual(output.read_bytes()[1024:1031], b'payload')
            with self.assertRaises(ValueError):
                pack.assemble(root / 'overlap', 4096, [(0, a), (1, b)])

    def test_prepare_resolves_dependency_before_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source, repository, inputs, keys = [root / n for n in ['source', 'repository', 'inputs', 'keys']]
            for directory in [source, repository, inputs, keys]:
                directory.mkdir()
            (source / 'build').mkdir()
            (source / 'build/envsetup.sh').write_text('source marker')
            (repository / 'replacement').write_bytes(b'fixed')
            (source / 'base').write_bytes(b'old')
            for role in prepare.ROLES:
                for suffix in ['.pk8', '.x509.pem']:
                    (keys / (role + suffix)).write_bytes(b'test fixture; never a usable signing key')
            digest = hashlib.sha256(b'fixed').hexdigest()
            manifest = {'files': [
                {'path': 'derived', 'sha256': digest, 'mode': 0o644, 'input': {'kind': 'source', 'path': 'base'}},
                {'path': 'base', 'sha256': digest, 'mode': 0o644, 'input': {'kind': 'repository', 'path': 'replacement'}}],
                'base_checks': {}, 'signing_link': 'device/roc/product/.private-signing', 'source_target': 'fixture-user'}
            (repository / 'build-support/public').mkdir(parents=True)
            (repository / 'build-support/public/source-manifest.json').write_text(json.dumps(manifest))
            (inputs / 'extraction.json').write_text(json.dumps({'passed': True, 'image_sha256': 'reference'}))
            def fake_load(name):
                return manifest if name == 'source-manifest.json' else {'reference_image': {'sha256': 'reference'}}
            with patch.object(prepare, 'REPO', repository), patch.object(prepare, 'load', fake_load), \
                 patch.object(prepare, 'run', return_value=type('Result', (), {'stdout': 'same public key'})()):
                prepare.prepare(source, inputs, keys, apply=False)
                self.assertEqual((source / 'base').read_bytes(), b'old')
                prepare.prepare(source, inputs, keys, apply=True)
            self.assertEqual((source / 'derived').read_bytes(), b'fixed')
            self.assertEqual((source / '.roc-public/before/base').read_bytes(), b'old')
            self.assertTrue((source / 'device/roc/product/.private-signing').is_symlink())

    def test_all_manifest_payloads_and_dependencies_are_available(self):
        manifest = common.load('source-manifest.json')
        by_path = {e['path']: e for e in manifest['files']}
        for entry in manifest['files']:
            self.assertEqual(len(entry['sha256']), 64)
            item = entry['input']
            self.assertFalse(entry['path'].endswith(('.pk8', '.temporary.pem')))
            if item['kind'] == 'repository':
                common.require_hash(common.inside(common.REPO, item['path']), entry['sha256'])
            elif item['kind'] == 'source' and item['path'] in by_path:
                self.assertEqual(entry['sha256'], by_path[item['path']]['sha256'])


if __name__ == '__main__':
    unittest.main()
