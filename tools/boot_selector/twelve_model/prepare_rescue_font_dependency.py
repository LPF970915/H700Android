"""Prepare one isolated binary Pillow wheel; no system/site package mutation."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    assert not args.work.exists() and not args.receipt.exists()
    assert sys.version_info[:2] == (3, 12) and platform.machine() == 'x86_64'
    args.work.mkdir(parents=True)
    request = urllib.request.Request('https://pypi.org/pypi/Pillow/11.3.0/json',
                                     headers={'User-Agent':'roc-h700-font-offline-builder/1'})
    metadata_bytes = urllib.request.urlopen(request, timeout=45).read()
    metadata = json.loads(metadata_bytes)
    assert metadata['info']['name'].lower() == 'pillow' and metadata['info']['version'] == '11.3.0'
    candidates = [item for item in metadata['urls'] if item['packagetype'] == 'bdist_wheel'
                  and 'cp312-cp312-manylinux' in item['filename'] and 'x86_64' in item['filename']]
    assert len(candidates) == 1, [item['filename'] for item in candidates]
    selected = candidates[0]
    assert urllib.parse.urlparse(selected['url']).hostname == 'files.pythonhosted.org'
    wheel_bytes = urllib.request.urlopen(selected['url'], timeout=45).read()
    digest = hashlib.sha256(wheel_bytes).hexdigest()
    assert digest == selected['digests']['sha256'] and len(wheel_bytes) == selected['size']
    wheel = args.work / selected['filename']
    wheel.write_bytes(wheel_bytes)
    (args.work/'pypi-metadata.json').write_bytes(metadata_bytes)
    environment = args.work / 'venv'
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(environment)],check=True)
    python = environment/'bin/python'
    target = Path(subprocess.check_output([str(python),'-c',
        'import sysconfig; print(sysconfig.get_paths()["purelib"])'],text=True).strip())
    assert target.resolve().is_relative_to(environment.resolve()) and target.is_dir()
    with zipfile.ZipFile(wheel) as archive:
        assert archive.testzip() is None
        for item in archive.infolist():
            relative = Path(item.filename)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert (target/relative).resolve().is_relative_to(target.resolve())
            assert not any(part.endswith('.data') for part in relative.parts)
        archive.extractall(target)
    result = json.loads(subprocess.check_output([str(python),'-c',
        'import PIL,PIL._imaging,pathlib,hashlib,json; p=pathlib.Path(PIL._imaging.__file__); '
        'print(json.dumps({"version":PIL.__version__,"core":str(p),'
        '"core_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))'],text=True))
    assert result['version'] == '11.3.0'
    record = {'passed':True,'python':str(python),'pillow':result,'wheel':str(wheel),
              'wheel_sha256':digest,'wheel_url':selected['url'],
              'metadata_sha256':hashlib.sha256(metadata_bytes).hexdigest(),
              'system_packages_changed':False,'existing_venv_changed':False,
              'source_compilation':False,'installation':'fresh venv without pip; verified binary wheel extraction',
              'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.receipt.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)


if __name__ == '__main__':
    main()
