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
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
PREFIX = 'device/roc/roc_os_source64/Navigation/'
SOURCE_DIRECTORY = 'src/com/roc/rgsp/navtrial/'
JAVA_PACKAGE = 'com.roc.rgsp.navtrial.'
HELPERS = {
    'AxisNavigation': 'AxisNavigationTest',
    'Direction': 'DirectionTest',
    'FocusIdentity': 'FocusIdentityTest',
    'MenuHotkey': 'MenuHotkeyTest',
    'MouseHotkey': 'Source64MouseHotkeyTest',
    'PointerPosition': 'PointerPositionTest',
    'StickVector': 'StickVectorTest',
    'KeyNavigation': 'KeyNavigationTest',
}
NAVIGATION_INPUTS = {
    'Android.bp', 'AndroidManifest.xml', 'res/xml/navigation_service.xml',
    *(SOURCE_DIRECTORY + name + '.java' for name in (*HELPERS, 'NavigationService', 'MouseController')),
}
RESUME_SCENARIOS = [
    'validated-blocked-MOVE-retained;channel-specific-neutral',
    'known-neutral-and-new-device-first-press;source-isolation',
    'screen-broadcast-retires-menu-select-document;fresh-hotkeys-recover',
    'live-interactive-keyguard-block-before-broadcast',
    'generation-guards-preserve-newer-menu-select-requests',
    'mouse-consumed-UP-balanced;old-Select-UP-does-not-toggle',
    'mouse-A-hold-live-lock-guard',
    'mouse-capture-records-blocked-axis-before-return',
    'stale-and-nonfinite-samples-do-not-unlock',
]
KEY_WRAPPER_SCENARIOS = [
    'managed-raw-DOWNs-use-local-400-160-timer',
    'absolute-10s-cap-requires-real-UP',
    'unmanaged-game-passthrough-and-window-owner',
    'axis-mouse-and-non-DPAD-buttons-preserved',
    'retired-and-reentrant-key-callbacks-cannot-resurrect',
    'live-power-keyguard-and-event-time-boundaries',
    'unavailable-Ring-observes-real-UP-and-preserves-canceled-debt',
]


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
    required = {PREFIX + name for name in NAVIGATION_INPUTS}
    resolved = {}
    for entry in recipe['files']:
        destination = entry.get('path')
        if not isinstance(destination, str) or not destination.startswith(PREFIX):
            continue
        if destination not in required:
            raise ValueError('Unexpected Navigation manifest source: ' + destination)
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


def snapshot_hashes(root):
    return {str(path): sha(path) for path in sorted(root.rglob('*')) if path.is_file()}


def validate_candidate(candidate, expected):
    if snapshot_hashes(candidate) != expected:
        raise AssertionError('Complete Navigation snapshot differs from the manifest')
    manifest = ET.parse(candidate / 'AndroidManifest.xml').getroot()
    android = '{http://schemas.android.com/apk/res/android}'
    if (manifest.get('package') != 'com.roc.rgsp.navtrial'
            or manifest.get(android + 'versionCode') != '18'
            or manifest.get(android + 'versionName') != '2.4-resume-guard'):
        raise AssertionError('Public host regressions require Navigation18 2.4-resume-guard')


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
                      'resume_checks': report['resume_checks'], 'resume_scenarios': 9,
                      'key_navigation_checks': report['key_navigation_checks'],
                      'key_wrapper_checks': report['key_wrapper_checks'], 'key_wrapper_scenarios': 7,
                      'Source64MouseHotkey': 'PASS', 'result': str(result)}))


def run_tests(args, work, report):
    javac, java = executable(args.javac), executable(args.java)
    manifest = args.manifest.resolve()
    manifest_sha = sha(manifest)
    sources = resolve_sources(manifest)
    assert sha(manifest) == manifest_sha, 'Manifest changed while resolving sources'
    test_root = Path(__file__).resolve().parent
    resume_runner = test_root / 'test_navigation_resume_candidate.py'
    legacy_extractor = test_root / 'test_navigation_service_fix.py'
    controls = [Path(__file__).resolve(), resume_runner, legacy_extractor]
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
    candidate, test_copy, classes = work / 'sources/Navigation', work / 'tests', work / 'classes'
    for directory in (candidate, test_copy, classes):
        directory.mkdir(parents=True)
    expected_candidate = {}
    for destination, item in sources.items():
        target = candidate / destination[len(PREFIX):]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item['path'], target)
        assert sha(target) == item['sha256']
        expected_candidate[str(target)] = item['sha256']
    expected_controls = {}
    for path in controls:
        target = test_copy / path.relative_to(test_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        assert sha(target) == control_sha[str(path)]
        expected_controls[str(target)] = control_sha[str(path)]
    validate_candidate(candidate, expected_candidate)
    assert snapshot_hashes(test_copy) == expected_controls, 'Test snapshot input set differs'
    report.update({'Navigation_snapshot': str(candidate), 'Navigation_snapshot_sha256': expected_candidate,
                   'test_snapshot_sha256': expected_controls})

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
    java_files = [candidate / SOURCE_DIRECTORY / (name + '.java') for name in HELPERS]
    java_files += [test_copy / path.relative_to(test_root) for path in tests.values()]
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
    fragment_work = work / 'service-fragments'
    fragment_result = fragment_work / 'result.json'
    fragment_script = test_copy / resume_runner.relative_to(test_root)
    command([sys.executable, '-B', fragment_script, '--candidate', candidate,
             '--javac', javac, '--java', java, '--work', fragment_work], 'service-fragments')
    fragments = json.loads(fragment_result.read_text())
    assert fragments['passed'] is True and fragments['hardware_reproduction'] is False
    assert fragments['emit_only'] is False, 'Generated fragments alone are not an execution pass'
    assert fragments['candidate_inputs_sha256'] == expected_candidate, 'Resume test used different candidate inputs'
    transitive_controls = (resume_runner, legacy_extractor, tests['AxisNavigation'], tests['KeyNavigation'])
    expected_transitive_controls = {str(test_copy / path.relative_to(test_root)): control_sha[str(path)]
                                    for path in transitive_controls}
    assert fragments['test_controls_sha256'] == expected_transitive_controls, 'Resume test controls differ'
    assert fragments['candidate_version'] == {
        'versionCode': 18, 'versionName': '2.4-resume-guard', 'diagnostics': 39}
    assert fragments['legacy_allowed_guard_stub'] is True
    assert fragments['static_checks'] and all(value is True for value in fragments['static_checks'].values())
    assert all(fragments[key] is False for key in
               ('device_accessed', 'production_modified', 'APK_built', 'HOME_fix_proven'))
    assert len(fragments['commands']) == 6
    assert all(item['returncode'] == 0 for item in fragments['commands'])
    assert re.search(r'^PASS: 79 production AxisNavigation state-machine checks\s*$',
                     fragments['commands'][1]['output'], re.M), 'Expected all 79 AxisNavigation checks'
    assert re.search(r'^PASS: 32 actual Service fragment checks\s*$',
                     fragments['commands'][2]['output'], re.M), 'Expected all 32 actual Service fragment checks'
    resume_output = fragments['commands'][3]['output']
    resume_pass = re.search(r'^PASS: (\d+) actual candidate resume fragment checks\s*$', resume_output, re.M)
    assert resume_pass and int(resume_pass.group(1)) > 0, 'Expected executed candidate resume checks'
    assert type(fragments['resume_checks']) is int and fragments['resume_checks'] == int(resume_pass.group(1))
    assert fragments['scenarios'] == RESUME_SCENARIOS
    assert re.findall(r'^SCENARIO (.+)$', resume_output, re.M) == RESUME_SCENARIOS
    key_navigation_pass = re.search(r'^PASS: (\d+) production KeyNavigation timing checks\s*$',
                                    fragments['commands'][4]['output'], re.M)
    key_wrapper_output = fragments['commands'][5]['output']
    key_wrapper_pass = re.search(r'^PASS: (\d+) actual candidate key wrapper checks\s*$', key_wrapper_output, re.M)
    assert key_navigation_pass and key_wrapper_pass, 'Expected executed physical key checks'
    assert type(fragments['key_navigation_checks']) is int and fragments['key_navigation_checks'] == int(key_navigation_pass.group(1)) > 0
    assert type(fragments['key_wrapper_checks']) is int and fragments['key_wrapper_checks'] == int(key_wrapper_pass.group(1)) > 0
    assert fragments['key_wrapper_scenarios'] == KEY_WRAPPER_SCENARIOS
    assert re.findall(r'^KEY_SCENARIO (.+)$', key_wrapper_output, re.M) == KEY_WRAPPER_SCENARIOS
    # Retain the original public result location for tooling that reads this receipt.
    public_fragment_result = work / 'service-fragments-result.json'
    shutil.copyfile(fragment_result, public_fragment_result)
    assert sha(public_fragment_result) == sha(fragment_result)
    assert sha(manifest) == manifest_sha, 'Manifest changed during test run'
    assert sha(manifest_snapshot) == manifest_sha, 'Manifest snapshot changed during test run'
    assert resolve_sources(manifest) == sources, 'Manifest input changed during test run'
    assert all(sha(path) == digest for path, digest in control_sha.items()), 'Test input changed'
    validate_candidate(candidate, expected_candidate)
    assert snapshot_hashes(test_copy) == expected_controls, 'Test snapshot changed during test run'
    assert sha(javac) == report['executables']['javac_sha256'] and sha(java) == report['executables']['java_sha256']
    report.update({'axis_checks': 79, 'service_fragment_checks': 32,
                   'resume_checks': fragments['resume_checks'], 'resume_scenarios': fragments['scenarios'],
                   'key_navigation_checks': fragments['key_navigation_checks'],
                   'key_wrapper_checks': fragments['key_wrapper_checks'],
                   'key_wrapper_scenarios': fragments['key_wrapper_scenarios'],
                   'legacy_allowed_guard_stub': True, 'Navigation_input_count': len(expected_candidate),
                   'service_fragment_result': str(public_fragment_result),
                   'service_fragment_result_sha256': sha(public_fragment_result),
                   'complete_candidate_and_transitive_test_inputs_verified': True,
                   'all_manifest_and_test_inputs_unchanged': True})


if __name__ == '__main__':
    main()
