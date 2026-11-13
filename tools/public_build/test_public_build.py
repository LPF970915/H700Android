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
import record_build
import validate_manifest


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

    def test_manifest_binding_rejects_stale_missing_or_failed_receipts(self):
        with tempfile.TemporaryDirectory() as t:
            repository = Path(t)
            support = repository / 'build-support/public'
            support.mkdir(parents=True)
            manifest = support / 'source-manifest.json'
            manifest.write_bytes(b'current source revision')
            current = common.sha(manifest)
            with patch.object(common, 'REPO', repository):
                self.assertEqual(common.require_manifest_binding(
                    {'passed': True, 'source_manifest_sha256': current}), current)
                for receipt in [
                    {'passed': True, 'source_manifest_sha256': '0' * 64},
                    {'passed': True},
                    {'passed': False, 'source_manifest_sha256': current},
                    {'passed': 'true', 'source_manifest_sha256': current},
                ]:
                    with self.assertRaisesRegex(ValueError, 'current public source manifest'):
                        common.require_manifest_binding(receipt)

    def test_prepared_tree_rejects_manifest_change(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            support = root / 'build-support/public'
            support.mkdir(parents=True)
            manifest = support / 'source-manifest.json'
            payload = b'revision one'
            manifest.write_text(json.dumps({'files': [
                {'path': 'staged', 'sha256': hashlib.sha256(payload).hexdigest(),
                 'bytes': len(payload), 'mode': 0o644}]}))
            source = root / 'source'
            marker = source / '.roc-public/prepare.json'
            marker.parent.mkdir(parents=True)
            (source / 'staged').write_bytes(payload)
            (source / 'staged').chmod(0o644)
            marker.write_text(json.dumps({'passed': True, 'source_manifest_sha256': common.sha(manifest)}))
            with patch.object(common, 'REPO', root), patch.object(record_build, 'REPO', root):
                self.assertTrue(record_build.prepared_receipt(source)['passed'])
                (source / 'staged').write_bytes(b'changed source')
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                    record_build.prepared_receipt(source)
                (source / 'staged').write_bytes(payload)
                (source / 'staged').chmod(0o600)
                with self.assertRaisesRegex(ValueError, 'mode mismatch'):
                    record_build.prepared_receipt(source)
                (source / 'staged').chmod(0o644)
                manifest.write_bytes(b'revision two')
                with self.assertRaisesRegex(ValueError, 'current public source manifest'):
                    record_build.prepared_receipt(source)

    def test_pack_rejects_stale_receipt_before_reading_images_or_creating_output(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            product = root / 'product'
            product.mkdir()
            (product / 'public-build.json').write_text(json.dumps({
                'passed': True, 'product': 'roc_os_release_candidate-user',
                'source_manifest_sha256': '0' * 64, 'images': {}}))
            output = root / 'output'
            args = type('Args', (), {'inputs': root / 'inputs', 'product': product, 'output': output})()
            with self.assertRaisesRegex(ValueError, 'current public source manifest'):
                pack.main(args)
            self.assertFalse(output.exists())

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
        result = validate_manifest.validate(common.SUPPORT / 'source-manifest.json')
        self.assertTrue(result['passed'])
        self.assertFalse(result['independent_clean_full_Android_build_passed'])

    def test_manifest_validation_rejects_duplicate_unsafe_or_changed_repository_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'payload').write_bytes(b'known source')
            entry = {'path': 'output', 'bytes': 12, 'mode': 0o644,
                     'sha256': common.sha(root / 'payload'),
                     'input': {'kind': 'repository', 'path': 'payload'}}
            manifest = {'files': [entry], 'signing_link': 'keys', 'base_checks': {},
                        'statistics': {'files': 1, 'new_payload_bytes': 0,
                                       'input_kinds': {'repository': 1}}}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest))
            self.assertTrue(validate_manifest.validate(path, root)['passed'])
            manifest['files'].append(dict(entry))
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Duplicate output path'):
                validate_manifest.validate(path, root)
            manifest['files'].pop()
            entry['path'] = '../escape'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Unsafe manifest path'):
                validate_manifest.validate(path, root)
            entry['path'] = 'output'
            entry['bytes'] = 13
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'byte count mismatch'):
                validate_manifest.validate(path, root)
            entry['bytes'] = 12
            path.write_text(json.dumps(manifest))
            (root / 'payload').write_bytes(b'stale source')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                validate_manifest.validate(path, root)

    def test_manifest_validation_rejects_copy_content_mismatch_and_cycles(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            entries = [{'path': name, 'bytes': 4, 'mode': 0o644, 'sha256': 'a' * 64,
                        'input': {'kind': 'source', 'path': other}}
                       for name, other in [('a', 'b'), ('b', 'a')]]
            manifest = {'files': entries, 'signing_link': 'keys', 'base_checks': {},
                        'statistics': {'files': 2, 'new_payload_bytes': 0, 'input_kinds': {'source': 2}}}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Copy dependency cycle'):
                validate_manifest.validate(path, root)
            entries[1]['sha256'] = 'b' * 64
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'different source content'):
                validate_manifest.validate(path, root)


if __name__ == '__main__':
    unittest.main()
