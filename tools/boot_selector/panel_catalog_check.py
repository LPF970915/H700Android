"""Fresh bounded original RG35XXH/current power and init execution audit.

Executes saved original Thumb bytes in Unicorn. GPIO is simulated RAM and all
display send/delay/API helpers are hooks. No hardware, image, or release-tool
changes. This is not proof of physical point-screen success.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import unicorn as uc
from unicorn import arm_const as ar

BASE = 0x4a000000
MODELS = {
    "current720": {"sha256": "a11271e1276173cee48bd5705d068fd8446cfc0ffb43fca70b3b6808c2e9d0db",
                   "power": 0x27c58, "printf": 0x6a7bc, "command": 0x27e3c, "data": 0x27fcc},
    "reference35h": {"sha256": "867700c6278bdcc70b3a335669f34f03c2cca1f240cd043be00310572551561d",
                     "power": 0x27688, "printf": 0x6b054, "command": 0x2786c, "data": 0x279fc},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def execute(binary, config, operation, branch):
    if len(binary) != 1048576 or sha(binary) != config["sha256"]:
        raise ValueError("Pinned original binary mismatch")
    cpu = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
    cpu.mem_map(BASE, 0x100000)
    cpu.mem_write(BASE, binary)
    cpu.mem_map(0x03000000, 0x100000)
    cpu.mem_map(0x70000000, 0x10000)
    # Physical strap expression in both saved originals: ((PE_DAT^64)>>6)&1.
    cpu.mem_write(0x0300b0a0, struct.pack("<I", 0 if branch else 64))
    initial_sp = 0x7000ff00
    return_to = BASE + 0x1000
    cpu.reg_write(ar.UC_ARM_REG_SP, initial_sp)
    cpu.reg_write(ar.UC_ARM_REG_LR, return_to | 1)
    for i in range(4, 12):
        cpu.reg_write(getattr(ar, "UC_ARM_REG_R" + str(i)), 0x12340000 + i * 0x100)
    saved = {i: cpu.reg_read(getattr(ar, "UC_ARM_REG_R" + str(i))) for i in range(4, 12)}
    cpu.reg_write(ar.UC_ARM_REG_R0, 0)
    events, writes, api_calls, returned = [], [], [], []
    helpers = {config['command']: 'COMMAND', config['data']: 'DATA', 0x2621c: 'WAIT_MS'}

    def code(machine, address, size, unused):
        offset = address - BASE
        if address == return_to:
            returned.append(True)
            machine.emu_stop()
            return
        if offset in helpers:
            events.append((helpers[offset], machine.reg_read(ar.UC_ARM_REG_R0) & 255))
        elif offset in (config['printf'], 0xe620, 0x26270, 0x262cc):
            api_calls.append({'offset': offset, 'r0': machine.reg_read(ar.UC_ARM_REG_R0),
                              'r1': machine.reg_read(ar.UC_ARM_REG_R1)})
        else:
            bounds = (0x262e4, 0x27a08) if operation == 'init' else (config['power'], config['power'] + 0x44)
            if not bounds[0] <= offset < bounds[1]:
                raise ValueError('Undeclared executed helper ' + hex(offset))
            return
        machine.reg_write(ar.UC_ARM_REG_PC, machine.reg_read(ar.UC_ARM_REG_LR))

    def write(machine, access, address, size, value, unused):
        if 0x03000000 <= address < 0x03100000:
            writes.append({'address': hex(address), 'size': size, 'value': value})

    cpu.hook_add(uc.UC_HOOK_CODE, code)
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE, write)
    start = 0x262e4 if operation == 'init' else config['power']
    cpu.emu_start(BASE + start + 1, BASE + 0x100000, count=10000, timeout=2_000_000)
    if returned != [True] or cpu.reg_read(ar.UC_ARM_REG_SP) != initial_sp:
        raise ValueError('Missing normal caller return or stack mismatch')
    if any(cpu.reg_read(getattr(ar, 'UC_ARM_REG_R' + str(i))) != value for i, value in saved.items()):
        raise ValueError('Callee-saved register mismatch')
    return {'operation': operation, 'branch': branch, 'events': events,
            'mmio_writes': writes, 'api_calls': api_calls,
            'returned': True, 'sp_and_callee_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--frozen-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = {'current720': args.current, 'reference35h': args.reference}
    result = {'passed': False, 'scope': __doc__, 'runs': {}, 'input_sha256': {}, 'unicorn': uc.__version__}
    frozen = json.loads(args.frozen_audit.read_text())
    for name, config in MODELS.items():
        binary = files[name].read_bytes()
        result['input_sha256'][name] = sha(binary)
        rows = [execute(binary, config, op, branch) for op in ('power', 'init') for branch in (0, 1)]
        expected_source = next(row for row in frozen['uboot'] if row['name'] == ('current_rg34xxsp' if name == 'current720' else 'reference_rg35xxh'))
        for row in rows:
            if row['operation'] == 'init':
                expected = [('WAIT_MS', 15), ('WAIT_MS', 50), ('WAIT_MS', 100)]
                expected += [(event['kind'], event['value']) for event in expected_source['branches']['boe' if row['branch'] else 'old']['events']]
                if row['events'] != expected:
                    raise ValueError('Fresh original init execution differs from frozen trace')
        result['runs'][name] = rows
    comparisons = []
    for op in ('power', 'init'):
        for branch in (0, 1):
            rows = [next(row for row in result['runs'][name] if row['operation'] == op and row['branch'] == branch) for name in MODELS]
            equal = rows[0]['mmio_writes'] == rows[1]['mmio_writes']
            if not equal:
                raise ValueError('Original GPIO sequence differs')
            comparisons.append({'operation': op, 'branch': branch, 'mmio_sequence_equal': equal,
                                'writes': len(rows[0]['mmio_writes'])})
    result['comparisons'] = comparisons
    result['passed'] = True
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'runs': 8, 'mmio_comparisons': comparisons}))


if __name__ == '__main__':
    main()
