"""Read the frozen boot DTB. Pin configuration is not a wakeup acceptance test."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained, regular, sha


def fdt_nodes(blob):
    header = struct.unpack_from('>10I', blob)
    assert header[0] == 0xd00dfeed and header[1] == len(blob)
    cursor, strings = header[2], header[3]
    end = cursor + header[9]
    assert end <= len(blob) and strings + header[8] <= len(blob)
    nodes, stack = {}, []
    while cursor < end:
        token, = struct.unpack_from('>I', blob, cursor)
        cursor += 4
        if token == 1:  # FDT_BEGIN_NODE
            zero = blob.index(0, cursor, end)
            stack.append(blob[cursor:zero].decode('ascii'))
            cursor = (zero + 4) & ~3
            nodes['/' + '/'.join(stack[1:])] = {}
        elif token == 2:
            assert stack
            stack.pop()
        elif token == 3:  # FDT_PROP
            length, name_offset = struct.unpack_from('>II', blob, cursor)
            cursor += 8
            name_start = strings + name_offset
            assert strings <= name_start < strings + header[8]
            zero = blob.index(0, name_start, strings + header[8])
            name = blob[name_start:zero].decode('ascii')
            assert cursor + length <= end and stack
            nodes['/' + '/'.join(stack[1:])][name] = blob[cursor:cursor + length]
            cursor = (cursor + length + 3) & ~3
        elif token == 4:  # FDT_NOP
            pass
        elif token == 9:
            assert not stack
            return nodes
        else:
            raise ValueError('Unknown FDT token')
    raise ValueError('FDT_END missing')


def main():
    constrained()
    out = REPO / 'out/rg34xxsp-readiness-20261102'
    lock = json.loads((REPO / 'docs/baselines/rg34xxsp-arm64-defaults-test2a-20261101/image-lock.json').read_text())
    expected = next(item for item in lock['ranges'] if item['name'] == 'prefix')
    prefix = Path('/home/lpf/h700-dualabi-image-20261031/prefix.candidate.raw')
    regular(prefix)
    assert prefix.stat().st_size == expected['bytes'] and sha(prefix) == expected['sha256']
    with prefix.open('rb') as f:
        f.seek(512)
        header = f.read(512)
        assert header[:8] == b'EFI PART'
        lba, count, size = struct.unpack_from('<QII', header, 72)
        assert count == 8 and size == 128
        f.seek(lba * 512)
        entries = f.read(count * size)
        boots = []
        for i in range(count):
            entry = entries[i * size:(i + 1) * size]
            if entry[56:128].decode('utf-16-le').split('\0')[0] != 'boot': continue
            first, last = struct.unpack_from('<QQ', entry, 32)
            assert first <= last and (last + 1) * 512 <= prefix.stat().st_size
            f.seek(first * 512)
            boots.append(f.read((last - first + 1) * 512))
    boot, = boots
    candidates, offset = [], 0
    while True:
        offset = boot.find(bytes.fromhex('d00dfeed'), offset)
        if offset < 0: break
        if offset + 40 <= len(boot):
            h = struct.unpack_from('>10I', boot, offset)
            if 40 < h[1] < 4 * 1024 * 1024 and offset + h[1] <= len(boot) and 16 <= h[5] <= 17:
                data = boot[offset:offset + h[1]]
                nodes = fdt_nodes(data)
                if any('hall_key' in props for props in nodes.values()): candidates.append((data, nodes))
        offset += 4
    blob, nodes = candidates.pop()
    assert not candidates, 'Ambiguous Hall DTB'
    path, props = next((path, props) for path, props in nodes.items() if 'hall_key' in props)
    cells = struct.unpack('>7I', props['hall_key'])
    controller = next(p for p in nodes.values() if p.get('phandle') == struct.pack('>I', cells[0]))
    assert controller['#gpio-cells'] == struct.pack('>I', 6)
    assert controller['compatible'].split(b'\0')[0] == b'allwinner,sun50iw9p1-pinctrl'
    assert cells[1:4] == (4, 7, 0), 'Unexpected Hall pin or function'
    native = Path('/home/lpf/h700-android10')
    reference = native / 'longan/kernel/linux-4.9/drivers/pinctrl/sunxi/pinctrl-sun50iw9p1.c'
    snippet = re.search(r'SUNXI_PIN\(SUNXI_PINCTRL_PIN\(E, 7\),(.*?)SUNXI_FUNCTION\(0x7', reference.read_text(), re.S)[1]
    assert 'SUNXI_FUNCTION_IRQ_BANK(0x6, 3, 7)' in snippet
    report = {'prefix_sha256': expected['sha256'], 'boot_sha256': hashlib.sha256(boot).hexdigest(),
        'dtb_sha256': hashlib.sha256(blob).hexdigest(), 'hall_node': path,
        'hall_pin': 'PE7', 'hall_function': 'gpio_in', 'powerkey_wakeup_rising_present': 'wakeup_rising' in props,
        'powerkey_wakeup_falling_present': 'wakeup_falling' in props,
        'reference_pinctrl_sha256': sha(reference), 'reference_pin_has_irq_function': True,
        'runtime_gpio_owner_verified': False, 'runtime_irq_wake_verified': False,
        'kernel_suspend_accepted': False, 'bringup_wakelock_changed': False,
        'kernel_or_dtb_modified': False}
    (out / 'power-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print('FROZEN_BOOT_HALL_PIN_AUDIT_PASS_PE7_NOT_WAKE_ACCEPTANCE', flush=True)


if __name__ == '__main__':
    main()
