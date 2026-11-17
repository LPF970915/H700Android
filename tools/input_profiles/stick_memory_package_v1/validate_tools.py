"""Run small ordinary-file fixtures; never build or inspect a card image."""
from pathlib import Path
import argparse
import ast
import copy
import gzip
import importlib.util
import json
import subprocess


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(output):
    here = Path(__file__).resolve().parent
    assert output.is_relative_to(here) and not output.exists()
    output.mkdir()
    package = load('stick_package_fixture', here / 'package.py')
    verify = load('stick_verify_fixture', here / 'verify.py')
    for path in here.glob('*.py'):
        ast.parse(path.read_text())
    image, old, new, label = [output / n for n in ('fixture.ext4', 'old.bin', 'new.bin', 'label.bin')]
    with image.open('xb') as writer:
        writer.truncate(16 * 1024**2)
    old.write_bytes(b'old payload\n')
    new.write_bytes(b'new payload differs\n')
    label.write_bytes(b'u:object_r:vendor_file:s0\0')
    process = subprocess.run(['/usr/sbin/mke2fs', '-t', 'ext4', '-m', '0', '-F', str(image)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (output / 'mke2fs.txt').write_text(process.stdout)
    assert process.returncode == 0
    paths = ['/', '/modules', '/bin', '/modules/test.ko', '/bin/test.sh']
    for command in ['mkdir /modules', 'mkdir /bin', f'write {old} /modules/test.ko',
                    f'write {old} /bin/test.sh']:
        package.debugfs(image, command, True)
    for path in paths:
        for name in ('atime', 'mtime', 'ctime', 'crtime'):
            package.debugfs(image, f'set_inode_field {path} {name} @1667520000', True)
            package.debugfs(image, f'set_inode_field {path} {name}_extra 0x12345678', True)
    for path in paths[-2:]:
        package.debugfs(image, f'ea_set -f {label} {path} security.selinux', True)
    before = {path: package.inode_times(package.debugfs(image, 'stat ' + path)) for path in paths}
    transcript = ''.join('debugfs: stat ' + json.dumps(path) + '\n' +
                         package.debugfs(image, 'stat ' + path) for path in paths)
    assert verify.time_inventory(transcript) == before
    before_meta = {path: package.metadata(image, path) for path in paths[-2:]}
    for path in paths[-2:]:
        package.install(image, new, path, before_meta[path], output, replace=True)
        for name, (seconds, extra) in before[path].items():
            package.debugfs(image, f'set_inode_field {path} {name} @{seconds}', True)
            package.debugfs(image, f'set_inode_field {path} {name}_extra 0x{extra:x}', True)
    after = {path: package.inode_times(package.debugfs(image, 'stat ' + path)) for path in paths}
    changed = [path for path in paths if before[path] != after[path]]
    assert before == after, 'Unrestored timestamp changes: ' + repr(changed)
    assert before_meta == {path: package.metadata(image, path) for path in paths[-2:]}
    process = subprocess.run(['/usr/sbin/e2fsck', '-f', '-n', str(image)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (output / 'e2fsck-readonly.txt').write_text(process.stdout)
    assert process.returncode == 0
    raw = b'fixture payload' * 11
    encoded = gzip.compress(raw, compresslevel=9, mtime=0)
    for tail in (0, 1, 3, 2048):
        assert gzip.decompress(encoded + bytes(tail)) == raw
    # Synthetic receipts exercise guard rejection only; these are not build
    # receipts and cannot be used as candidate input manifests.
    memory = {'schema': 'roc.h700.swap2g-host.v1', 'passed': True,
              'swap_bytes': 2147483648, 'default_enabled': True,
              'physical_acceptance': False, 'actual_host_swapon': False,
              'helper_sha256': package.sha(new), 'reuse_size_or_space_guard': True,
              'failure_nonfatal': True, 'no_RAM_identity_gate': True,
              'controls': {str(new): package.sha(new)}}
    mutations = {'schema': 'wrong', 'passed': False, 'swap_bytes': 1073741824,
                 'default_enabled': False, 'physical_acceptance': True,
                 'actual_host_swapon': True, 'helper_sha256': '0' * 64,
                 'reuse_size_or_space_guard': False, 'failure_nonfatal': False,
                 'no_RAM_identity_gate': False, 'controls': {}}
    memory_cases = 0
    for module in (package, verify):
        module.memory_check(memory, new)
        memory_cases += 1
        for key, value in mutations.items():
            bad = copy.deepcopy(memory)
            bad[key] = value
            try:
                module.memory_check(bad, new)
            except (ValueError, KeyError):
                memory_cases += 1
            else:
                raise AssertionError('Guard accepted mutation: ' + key)
        bad = copy.deepcopy(memory)
        bad['controls'] = {str(new): '0' * 64}
        try:
            module.memory_check(bad, new)
        except ValueError:
            memory_cases += 1
        else:
            raise AssertionError('Guard accepted changed control')
    (output / 'result.json').write_text(json.dumps({
        'schema': 'roc.h700.stick-memory-package-tools-fixture.v1', 'passed': True,
        'AST_and_imports': True, 'ordinary_ext4_bytes': image.stat().st_size,
        'independent_timestamp_transcript_parser': True,
        'actual_debugfs_rm_write': True, 'replacement_owner_mode_label_preserved': True,
        'all_five_inode_timestamp_sets_preserved': True,
        'nonzero_ext4_timestamp_extra_preserved': True,
        'readonly_e2fsck_passed': True, 'python_zero_gzip_tails': [0, 1, 3, 2048],
        'synthetic_memory_guard_cases': memory_cases, 'actual_host_swapon': False,
        'source_sha256': {p.name: package.sha(p) for p in here.glob('*.py')},
        'no_card_device_or_Test8_access': True,
    }, indent=2) + '\n')
    print('STICK_MEMORY_PACKAGE_TOOLS_FIXTURE_PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
