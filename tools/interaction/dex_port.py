"""Small offline DEX port utility; original archives and disassembly stay intact."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

def canonical(text):
    # The assembler may attach an unchanged debug line to the preceding label.
    # Debug line placement is not an executable instruction or field value.
    text = re.sub(r'(?m)^\s*\.line \d+\s*$', '', text)
    text = re.sub(r'(?m)^(\.field [^\n]*\bstatic\b[^\n]*:[L\[][^\n]*) = null$', r'\1', text)
    text = re.sub(r'(?m)^(\.field [^\n]*\bstatic\b[^\n]*:Z) = false$', r'\1', text)
    text = re.sub(r'const-string/jumbo\b', 'const-string', text)
    text = re.sub(r'goto/(?:16|32)\b', 'goto', text)
    labels = re.findall(r'(?m)^\s*(:[A-Za-z_][A-Za-z_0-9]*)\s*$', text)
    mapping = {s: ':label_' + str(i) for i, s in enumerate(dict.fromkeys(labels))}
    text = re.sub(r'"(?:\\.|[^"\\])*"|:[A-Za-z_][A-Za-z_0-9]*\b', lambda m: mapping.get(m[0], m[0]), text)
    return '\n'.join(s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#'))

def methods(text):
    return {m.group(1).split()[-1]: m.group(0) for m in re.finditer(
        r'^\.method ([^\n]+)\n.*?^\.end method', text, re.M | re.S)}

def equivalent_class(expected, actual):
    """Compare definitions irrespective of method order and locals/registers notation."""
    before, after = methods(expected), methods(actual)
    if set(before) != set(after):
        return False
    def method_canonical(text):
        header = text.splitlines()[0]
        signature = header.split()[-1]
        params = signature.split('(', 1)[1].split(')', 1)[0]
        words = 0 if 'static' in header.split() else 1
        for token in re.findall(r'\[*(?:L[^;]+;|[ZBCSIFJD])', params):
            words += 2 if token in ('J', 'D') else 1
        text = re.sub(r'(?m)^(\s*)\.locals (\d+)\s*$',
                      lambda m: m[1] + '.registers ' + str(int(m[2]) + words), text)
        return canonical(text)
    for name in before:
        if method_canonical(before[name]) != method_canonical(after[name]):
            return False
    remove_methods = lambda text: re.sub(r'^\.method [^\n]+\n.*?^\.end method', '', text, flags=re.M | re.S)
    return canonical(remove_methods(expected)) == canonical(remove_methods(actual))

class DexPort:
    def __init__(self, repo, work):
        self.repo, self.work = Path(repo), Path(work)
        self.work.mkdir(exist_ok=False)
        native = Path('/home/lpf/h700-android10/android')
        self.jdk = native / 'prebuilts/jdk/jdk9/linux-x86/bin'
        self.apktool = Path('/home/lpf/h700-at4k-20261028/apktool-2.9.3.jar')
        assert hashlib.sha256(self.apktool.read_bytes()).hexdigest() == '7956eb04194300ce0d0a84ad18771eebc94b89fb8d1ddcce8ea4c056818646f4'
        self.run(self.jdk / 'javac', '-J-Xmx512m', '-cp', self.apktool, '-d', self.work,
                 self.repo / 'tools/rotation/FrameworkDexTool.java', self.repo / 'tools/interaction/FrameworkApiAudit.java')
        self.java = ['taskset', '-c', '0', self.jdk / 'java', '-Xmx2g', '-cp',
                     str(self.work) + ':' + str(self.apktool), 'FrameworkDexTool']
        self.entries = {}

    def run(self, *args):
        print('DEX_PORT', *map(str, args[:3]), flush=True)
        p = subprocess.run(list(map(str, args)), capture_output=True)
        if p.returncode:
            raise RuntimeError(p.stdout.decode(errors='replace')[-6000:] + p.stderr.decode(errors='replace')[-6000:])
        return p.stdout.decode(errors='replace') + p.stderr.decode(errors='replace')

    def load(self, archive, names, label):
        entries = {}
        for name in names:
            found = self.run(*self.java, 'find', archive, 'L' + name + ';')
            matches = re.findall(r'CLASS_ENTRY=(.+)', found)
            assert len(matches) == 1, (name, found)
            entries[name] = matches[0]
        for entry in set(entries.values()):
            directory = self.work / (label + '-original-' + entry)
            self.run(*self.java, 'disassemble', archive, entry, directory)
        self.entries[label] = entries
        return {name: (self.work / (label + '-original-' + entry) / (name + '.smali')).read_text()
                for name, entry in entries.items()}

    def emit(self, source, label, changed, added, output):
        original_entries = self.entries[label]
        extra = self.work / 'extra'
        extra.mkdir()
        byentry = {}
        for name, text in {**changed, **added}.items():
            target = extra / (name + '.smali')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            if name in changed:
                byentry.setdefault(original_entries[name], []).append(name)
        rebuilt = {}
        compared = 0
        for entry, names in byentry.items():
            original = self.work / (label + '-original-' + entry)
            modified = self.work / ('modified-' + entry)
            shutil.copytree(original, modified)
            for name in names:
                (modified / (name + '.smali')).unlink()
            dex = self.work / entry
            self.run(*self.java, 'assemble', modified, dex)
            verify = self.work / ('verify-' + entry)
            jar = self.work / ('verify-' + entry + '.jar')
            with zipfile.ZipFile(jar, 'w') as z:
                z.write(dex, entry)
            self.run(*self.java, 'disassemble', jar, entry, verify)
            for before in original.rglob('*.smali'):
                relative = before.relative_to(original)
                if relative.as_posix().removesuffix('.smali') in names:
                    continue
                assert canonical(before.read_text()) == canonical((verify / relative).read_text()), relative
                compared += 1
            rebuilt[entry] = dex
        with zipfile.ZipFile(source) as z:
            indices = [1 if n == 'classes.dex' else int(re.search(r'classes(\d+)\.dex', n)[1])
                       for n in z.namelist() if re.fullmatch(r'classes\d*\.dex', n)]
        extra_entry = 'classes' + str(max(indices) + 1) + '.dex'
        self.run(*self.java, 'assemble', extra, self.work / extra_entry)
        with zipfile.ZipFile(self.work / 'extra.jar', 'w') as z:
            z.write(self.work / extra_entry, extra_entry)
        verify = self.work / 'extra-verify'
        self.run(*self.java, 'disassemble', self.work / 'extra.jar', extra_entry, verify)
        expected_files = {p.relative_to(extra) for p in extra.rglob('*.smali')}
        assert expected_files == {p.relative_to(verify) for p in verify.rglob('*.smali')}
        for relative in expected_files:
            assert equivalent_class((extra / relative).read_text(), (verify / relative).read_text()), relative
        rebuilt[extra_entry] = self.work / extra_entry
        with zipfile.ZipFile(source) as a, zipfile.ZipFile(output, 'w') as b:
            for info in a.infolist():
                b.writestr(info, rebuilt[info.filename].read_bytes() if info.filename in rebuilt else a.read(info.filename))
            b.write(rebuilt[extra_entry], extra_entry)
        with zipfile.ZipFile(source) as a, zipfile.ZipFile(output) as b:
            for name in a.namelist():
                if name not in rebuilt:
                    assert a.read(name) == b.read(name), name
        return {'unchanged_classes_compared': compared, 'changed_classes': sorted(changed),
                'added_classes': sorted(added), 'non_modified_zip_entries_unchanged': True,
                'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest()}
