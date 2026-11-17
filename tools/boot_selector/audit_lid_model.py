"""Independent read-only final APK/source-connection audit; no build or image edits."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
import zipfile
import zlib


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory
    result = json.loads((directory / 'build-result.json').read_text())
    assert result['passed'] is True
    apk = directory / 'ROCReleaseLid3_ModelGate.apk'
    assert digest(apk.read_bytes()) == result['artifact_sha256']
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert [n for n in names if n.endswith('.dex')] == ['classes.dex']
        dex = archive.read('classes.dex')
    assert dex[:8] == b'dex\n038\0'
    assert struct.unpack_from('<I', dex, 32)[0] == len(dex)
    assert dex[12:32] == hashlib.sha1(dex[32:]).digest()
    assert struct.unpack_from('<I', dex, 8)[0] == zlib.adler32(dex[12:]) & 0xffffffff
    assert digest(dex) == result['dex_normalization']['normalized_sha256']
    raw = (directory / 'classes.d8-raw.dex').read_bytes()
    assert raw[:8] == dex[:8] and raw[32:] == dex[32:]
    disasm = (directory / 'dexdump.txt').read_text(encoding='utf-8')
    service = disasm.split("Class descriptor  : 'Lcom/roc/rgsp/lid/LidService;'", 1)[1]
    supported = service.split("name          : 'supported'", 1)[1]
    supported = supported.split('    #', 1)[0]
    for required in ['ro.boot.roc_model', 'ro.boot.roc_clamshell', 'ro.product.device',
                     'persist.vendor.rgsp.input_profile', 'Lcom/roc/rgsp/lid/LidProfile;.supported:']:
        assert required in supported, required
    assert supported.count('Lcom/roc/rgsp/lid/LidProfile;.supported:') == 1
    lock = json.loads((directory / 'input-lock.json').read_text())
    candidate = directory / 'candidate-source'
    actual = {p.relative_to(candidate).as_posix(): digest(p.read_bytes())
              for p in sorted(candidate.rglob('*')) if p.is_file()}
    assert actual == lock['candidate_sha256']
    assert set(actual) - set(lock['original_sha256']) == {'src/com/roc/rgsp/lid/LidProfile.java'}
    changed = [p for p in lock['original_sha256'] if actual[p] != lock['original_sha256'][p]]
    assert changed == ['AndroidManifest.xml', 'src/com/roc/rgsp/lid/LidService.java']
    semantics = json.loads((directory / 'semantic-tests.json').read_text())
    assert semantics['passed'] and semantics['model_gate_checks'] == 34
    assert semantics['actual_compiled_LidState_checks'] == 3613
    assert 'LID_MODEL_PROFILE_PASS checks=34' in (directory / 'model-tests.txt').read_text()
    assert 'UNIVERSAL_HALL_EDGE_PASS checks=3613' in (directory / 'state-tests.txt').read_text()
    for name in ['old-signature.txt', 'new-signature.txt']:
        text = (directory / name).read_text()
        assert re.findall(r'certificate SHA-256 digest: (\w+)', text) == [result['platform_certificate_sha256']]
        assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in text
    receipt = {'passed': True, 'apk_sha256': digest(apk.read_bytes()),
               'actual_final_dex_integrity': True, 'actual_Service_supported_calls_model_gate_once': True,
               'actual_Service_reads_both_boot_properties': True, 'candidate_snapshot_exact': True,
               'source_changes_only_manifest_gate_and_helper': True, 'state_machine_source_unchanged': True,
               'same_verified_platform_signer_receipts': True, 'model_checks': 34, 'state_checks': 3613,
               'scope': 'Read-only final artifact and compiled-disassembly connection checks; no hardware acceptance.'}
    (directory / 'independent-artifact-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
