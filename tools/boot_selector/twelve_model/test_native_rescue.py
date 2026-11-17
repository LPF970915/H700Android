"""Exercise manual volume trial in final host/A64 ELFs on ordinary fixtures."""
from pathlib import Path
import hashlib
import json
import os
import struct
import subprocess
import time

from models import ALL_MODEL_IDS, MODEL_METADATA

CYCLE = ('rg35xxh', 'rg34xxsp', 'rgcubexx')


def target_for(model, direction):
    geometry = MODEL_METADATA[model]['geometry']
    current = {'640x480': 0, '720x480': 1, '720x720': 2}[geometry]
    return CYCLE[(current + (1 if direction == 'down' else -1)) % 3]


def exercise(host, arm, output, runtime_directory):
    output.mkdir()
    runtime_directory.mkdir()
    commands = [('host', [str(host)]), ('aarch64', ['/usr/bin/qemu-aarch64', str(arm)])]
    previews = []
    for model_index, model in enumerate(ALL_MODEL_IDS):
        meta = MODEL_METADATA[model]
        highlighted = ALL_MODEL_IDS[(model_index + 2) % len(ALL_MODEL_IDS)]
        for direction in ('down', 'up'):
            target = target_for(model, direction)
            for architecture, command in commands:
                stem = f'{model}-{direction}-{architecture}'
                ppm, result = output / (stem + '.ppm'), output / (stem + '.json')
                script = 'DAURR' + ('N' if direction == 'down' else 'P')
                completed = subprocess.run([*command, '--simulate', 'x'.join(map(str, meta['native_size'])),
                    '--initial-model', model, '--rotation', str(meta['display_rotation']),
                    '--ppm', str(ppm), '--script', script, '--output', str(result)],
                    capture_output=True, text=True, timeout=8)
                expected = {'schema': 2, 'model_id': target, 'save_default': False}
                assert completed.returncode == 4 and json.loads(result.read_text()) == expected, (
                    model, direction, architecture, completed.returncode, completed.stderr)
                previews.append({'architecture': architecture, 'active_model': model,
                    'highlighted_model': highlighted, 'direction': direction, 'target_model': target,
                    'script': script, 'save_was_enabled_before_preview': True,
                    'result': expected, 'returncode': completed.returncode, 'pass': True,
                    'ppm_sha256': hashlib.sha256(ppm.read_bytes()).hexdigest()})
    blind = []
    for architecture, command in commands:
        for framebuffer in ('missing', 'regular'):
            case = output / ('blind-' + architecture + '-' + framebuffer)
            case.mkdir()
            io_case = runtime_directory / case.name
            io_case.mkdir()
            fifo, fb, result = io_case / 'event0', case / 'fb0', case / 'result.json'
            os.mkfifo(fifo)
            if framebuffer == 'regular':
                fb.write_bytes(b'ordinary file; not an fbdev ioctl endpoint')
            fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
            proc = subprocess.Popen([*command, '--fb', str(fb), '--inputs', str(fifo),
                '--initial-model', 'rg35xxh', '--output', str(result), '--timeout', '5'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            def event(code, value):
                # Both host and static AArch64 use the 64-bit input_event ABI.
                os.write(fd, struct.pack('<qqHHi', 0, 0, 1, code, value))

            try:
                time.sleep(0.15)
                for code in (108, 108, 304):  # DOWN, DOWN, physical A
                    event(code, 1)
                    event(code, 0)
                time.sleep(0.15)
                assert proc.poll() is None and not result.exists(), 'Blind ordinary Start escaped'
                event(114, 1)
                time.sleep(0.08)
                event(114, 2)  # kernel repeat cannot trigger another preview
                time.sleep(0.04)
                assert proc.poll() is None and not result.exists(), 'Trial happened before release'
                event(114, 0)
                stdout, stderr = proc.communicate(timeout=8)
                expected = {'schema': 2, 'model_id': 'rg34xxsp', 'save_default': False}
                assert proc.returncode == 4 and json.loads(result.read_text()) == expected, (
                    architecture, framebuffer, proc.returncode, stdout, stderr)
                (case / 'stdout.txt').write_text(stdout)
                (case / 'stderr.txt').write_text(stderr)
                blind.append({'architecture': architecture, 'framebuffer': framebuffer,
                    'active_model': 'rg35xxh', 'direction': 'down', 'normal_confirm_blocked': True,
                    'result_before_volume': False, 'input_FIFO_ordinary': True,
                    'input_FIFO_path':str(fifo),
                    'hardware_accessed': False, 'returncode': proc.returncode,
                    'result': expected, 'passed': True})
            finally:
                os.close(fd)
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=8)
    return {'profile_cycle': list(CYCLE), 'preview_cases': previews, 'blind_runtime_cases': blind,
            'host_and_actual_aarch64': True, 'hardware_accessed': False,
            'runtime_FIFO_is_ordinary_fixture': True}
