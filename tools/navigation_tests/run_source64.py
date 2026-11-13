"""Run the public Source64 navigation host regressions without Android or keys.

Sources are resolved exclusively through the public source manifest and copied
into a fresh work directory after size/SHA256 checks. Use run-limited.sh when
running on the project's Linux build host. No APK or device test is performed.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
PREFIX = 'device/roc/roc_os_source64/Navigation/src/com/roc/rgsp/navtrial/'
JAVA_PACKAGE = 'com.roc.rgsp.navtrial.'
HELPERS = {
    'AxisNavigation': 'AxisNavigationTest',
    'Direction': 'DirectionTest',
    'FocusIdentity': 'FocusIdentityTest',
    'MenuHotkey': 'MenuHotkeyTest',
    'MouseHotkey': 'Source64MouseHotkeyTest',
    'PointerPosition': 'PointerPositionTest',
    'StickVector': 'StickVectorTest',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository_file(name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts or '\\' in name:
        raise ValueError('Unsafe repository input path: ' + name)
    path = REPO.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(REPO.resolve()) or path.is_symlink() or not path.is_file():
        raise ValueError('Repository input must be a regular contained file: ' + name)
    return path


def resolve_sources(manifest):
    recipe = json.loads(manifest.read_text(encoding='utf-8'))
    if recipe.get('schema') != 1 or not isinstance(recipe.get('files'), list):
        raise ValueError('Unsupported public source manifest')
    required = {PREFIX + name + '.java' for name in (*HELPERS, 'NavigationService')}
    resolved = {}
    for entry in recipe['files']:
        destination = entry.get('path')
        if destination not in required:
            continue
        if destination in resolved:
            raise ValueError('Duplicate manifest source: ' + destination)
        origin = entry.get('input', {})
        if origin.get('kind') != 'repository':
            raise ValueError('Host navigation tests require a public repository input: ' + destination)
        path = repository_file(origin['path'])
        digest = sha(path)
        if path.stat().st_size != entry['bytes'] or digest != entry['sha256']:
            raise ValueError('Manifest size/SHA256 mismatch: ' + destination)
        resolved[destination] = {'path': str(path), 'repository_path': origin['path'],
                                 'sha256': digest, 'bytes': path.stat().st_size}
    if set(resolved) != required:
        raise ValueError('Manifest sources missing: ' + str(sorted(required - set(resolved))))
    return resolved


def executable(value):
    found = shutil.which(value)
    if not found:
        raise ValueError('Host executable not found: ' + value)
    return str(Path(found).resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=REPO / 'build-support/public/source-manifest.json')
    parser.add_argument('--javac', default='javac', help='Host javac executable or path')
    parser.add_argument('--java', default='java', help='Matching host java executable or path')
    parser.add_argument('--work', type=Path, required=True, help='New directory; existing output is rejected')
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    report = {'schema': 1, 'passed': False, 'test_type': 'public_source64_host_regressions',
              'work': str(work), 'device_accessed': False, 'APK_built': False,
              'hardware_reproduction': False, 'private_keys_used': False,
              'framework_boundary': 'Service fragments execute with virtual Android stubs'}
    result = work / 'result.json'
    try:
        run_tests(args, work, report)
        report['passed'] = True
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        result.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'axis_checks': 79, 'service_fragment_checks': 32,
                      'Source64MouseHotkey': 'PASS', 'result': str(result)}))


def run_tests(args, work, report):
    javac, java = executable(args.javac), executable(args.java)
    manifest = args.manifest.resolve()
    sources = resolve_sources(manifest)
    manifest_sha = sha(manifest)
    test_root = Path(__file__).resolve().parent
    controls = [Path(__file__).resolve(), test_root / 'test_navigation_service_fix.py']
    tests = {name: test_root / 'com/roc/rgsp/navtrial' / (test + '.java')
             for name, test in HELPERS.items()}
    controls.extend(tests.values())
    control_sha = {str(path): sha(path) for path in controls}
    report.update({'manifest': str(manifest), 'manifest_sha256': manifest_sha,
                   'resolved_sources': sources, 'test_inputs_sha256': control_sha,
                   'executables': {'javac': javac, 'java': java,
                                   'javac_sha256': sha(javac), 'java_sha256': sha(java)},
                   'commands': []})
    manifest_snapshot = work / 'source-manifest.json'
    shutil.copyfile(manifest, manifest_snapshot)
    assert sha(manifest_snapshot) == manifest_sha
    candidate, test_copy, classes = work / 'sources', work / 'tests', work / 'classes'
    for directory in (candidate, test_copy, classes):
        directory.mkdir()
    for destination, item in sources.items():
        target = candidate / PurePosixPath(destination).name
        shutil.copyfile(item['path'], target)
        assert sha(target) == item['sha256']
    for path in controls:
        target = test_copy / path.name
        shutil.copyfile(path, target)
        assert sha(target) == control_sha[str(path)]

    def command(argv, name):
        process = subprocess.run([str(value) for value in argv], text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        log = work / (name + '.log')
        log.write_text(process.stdout, encoding='utf-8', newline='\n')
        report['commands'].append({'argv': [str(value) for value in argv],
                                   'returncode': process.returncode, 'log': str(log),
                                   'log_sha256': sha(log)})
        if process.returncode:
            raise RuntimeError(name + ' failed; see ' + str(log))
        return process.stdout

    command([javac, '-version'], 'javac-version')
    command([java, '-version'], 'java-version')
    java_files = [candidate / (name + '.java') for name in HELPERS]
    java_files += [test_copy / path.name for path in tests.values()]
    command([javac, '-J-Xmx512m', '-encoding', 'UTF-8', '-source', '8', '-target', '8',
             '-d', classes, *java_files], 'compile-helpers')
    outcomes = {}
    for helper, test in HELPERS.items():
        output = command([java, '-Xmx256m', '-cp', classes, JAVA_PACKAGE + test], test)
        success = (re.search(r'^MenuHotkeyTest PASS\s*$', output, re.M) if helper == 'MenuHotkey'
                   else re.search(r'^PASS:', output, re.M))
        if not success:
            raise AssertionError('Missing explicit PASS from ' + test)
        if helper == 'AxisNavigation' and not re.search(
                r'^PASS: 79 production AxisNavigation state-machine checks\s*$', output, re.M):
            raise AssertionError('Expected all 79 production AxisNavigation checks')
        outcomes[test] = output.strip()
    report['helper_results'] = outcomes
    fragment_result = work / 'service-fragments-result.json'
    fragment_script = test_copy / 'test_navigation_service_fix.py'
    command([sys.executable, '-B', fragment_script,
             '--source', candidate / 'NavigationService.java', '--axis', candidate / 'AxisNavigation.java',
             '--javac', javac, '--java', java, '--work', work / 'service-fragments',
             '--result', fragment_result], 'service-fragments')
    fragments = json.loads(fragment_result.read_text())
    assert fragments['passed'] is True and fragments['hardware_reproduction'] is False
    assert fragments['source_sha256'] == sources[PREFIX + 'NavigationService.java']['sha256']
    assert fragments['axis_sha256'] == sources[PREFIX + 'AxisNavigation.java']['sha256']
    assert fragments['test_script_sha256'] == control_sha[str(test_root / 'test_navigation_service_fix.py')]
    assert re.search(r'^PASS: 32 actual Service fragment checks\s*$',
                     fragments['commands'][-1]['output'], re.M), 'Expected all 32 actual Service fragment checks'
    assert sha(manifest) == manifest_sha, 'Manifest changed during test run'
    assert resolve_sources(manifest) == sources, 'Manifest input changed during test run'
    assert all(sha(path) == digest for path, digest in control_sha.items()), 'Test input changed'
    report.update({'axis_checks': 79, 'service_fragment_checks': 32,
                   'service_fragment_result': str(fragment_result),
                   'service_fragment_result_sha256': sha(fragment_result),
                   'all_manifest_and_test_inputs_unchanged': True})


if __name__ == '__main__':
    main()
