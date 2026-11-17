"""Execute the final ordinary prefix through the real U-Boot Linux DTB handoff.

Physical peripherals, environment storage, console and architecture flag remain
explicit isolated fixtures. No card, USB, serial or device path is accessed.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import stat
import struct
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
PROOF = ROOT / 'out/test6-fastboot-readonly-20261116/independent-final-handoff-v4/audit.py'
PARSER = ROOT / 'out/boot-selector-integration-20261114/actual-uboot-parser-v1'
PINNED = {
    PROOF: 'c40df9d456efad535c23b8df4ae63fb82acf5e0a307fb4085b6f0261d7853d5e',
    PARSER / 'probe.py': '872801837929835d0f02fda19bb4f055596024d5ee2f6691f0992c75cd10d747',
    PARSER / 'real_fdt_probe.py': 'c0e6b4f47f7ef80bc72eb393c0d52b4cba15e637703bb6726c3af750290639ac',
}
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/release'), str(PARSER)]
from package_h700_v6a import constrained
from h700_panel_boot import decode_env, ENV_OFFSET, ENV_SIZE
from rg35xxh_display import (BOOT_OFFSET, BOOT_BYTES, TOC_OFFSET, TOC_BYTES,
                            PREFIX_BYTES, fdt_properties, read_toc)
from probe import BASE, GD, RETURN, Execution, command_table
from models import ALL_MODEL_IDS, MODEL_METADATA, MODEL_PROFILE, PROPERTIES, VALUES


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ordinary(path):
    require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode),
            'Only ordinary non-symlink files may supply prefix and sources')
    return path.read_bytes()


def word(e, address):
    return struct.unpack('<I', e.uc.mem_read(address, 4))[0]


def reserve_invoke(e, offset):
    e.returned = False
    for register, value in e.initial_regs.items():
        e.uc.reg_write(register, value)
    e.uc.reg_write(e.a.UC_ARM_REG_SP, e.sp)
    e.uc.reg_write(e.a.UC_ARM_REG_R0, 0)
    e.uc.reg_write(e.a.UC_ARM_REG_LR, RETURN | 1)
    e.uc.emu_start((e.base + offset) | 1, RETURN + 2,
                   timeout=10_000_000, count=10_000_000)
    require(e.returned and not e.invalid_memory, 'Exact reserve/relocate normal return')
    require(e.uc.reg_read(e.a.UC_ARM_REG_SP) == e.sp and all(
        e.uc.reg_read(r) == v for r, v in e.initial_regs.items()), 'Reserve/relocate ABI')
    return e.uc.reg_read(e.a.UC_ARM_REG_R0)


def reserve_control(blob, table, fdt, dtbo, slide):
    e = Execution(blob, table, {}, slide)
    initial, reserve_sp = 0x47000000, 0x47f00000
    e.uc.mem_map(initial, 0x1000000)
    e.uc.mem_map(BASE + 0x100000, 0x10000)
    e.uc.mem_write(initial, fdt)
    e.uc.mem_write(BASE + 0x100000, dtbo)
    e.uc.mem_write(GD + 0x5c, struct.pack('<I', initial))
    e.uc.mem_write(GD + 0x50, struct.pack('<I', reserve_sp))
    require(reserve_invoke(e, 0xef5c) == 0, 'Actual reserve_fdt success')
    total = struct.unpack_from('>I', fdt, 4)[0]
    expected = (total + 0x101f) & ~31
    size, destination = word(e, GD + 0x68), word(e, GD + 0x60)
    require(size == expected and destination == reserve_sp - size, 'Actual FDT reservation range')
    source = bytes(e.uc.mem_read(initial, size))
    require(struct.unpack_from('>I', source, 4)[0] == size, 'Actual capacity header grown')
    require(reserve_invoke(e, 0xeee8) == 0 and word(e, GD + 0x5c) == destination,
            'Actual relocate_fdt installs runtime control')
    relocated = bytes(e.uc.mem_read(destination, size))
    require(relocated == source, 'Actual reserve relocation full byte equality')
    return relocated, {'slide': slide, 'bytes': size, 'sha256': sha(relocated),
                       'actual_reserve_and_relocate': True}


def tree(e, address):
    data = bytes(e.uc.mem_read(address, 0x30000))
    total, props = fdt_properties(data)
    def integer(name):
        return int.from_bytes(props[name]['data'], 'big')
    return {'address': hex(address), 'total': total, 'sha256': sha(data[:total]),
            'initrd': {name: integer('/chosen/' + name) for name in (
                'linux,initrd-start', 'linux,initrd-end')},
            'panel': {name: integer('/soc@03000000/lcd0@01c0c000/' + name)
                      for name in PROPERTIES},
            'bootargs': props.get('/chosen/bootargs', {}).get('data', b'').rstrip(b'\0').decode('ascii')}


def expected_args(model, route):
    metadata = MODEL_METADATA[model]
    width, height = metadata['geometry'].split('x')
    return {'roc_model': model, 'roc_route': route,
            'roc_clamshell': str(int(metadata['lid'])), 'roc_sticks': str(metadata['sticks']),
            'roc_form_factor': metadata['form_factor'],
            'roc_native_width': str(metadata['native_size'][0]),
            'roc_native_height': str(metadata['native_size'][1]),
            'roc_logical_width': width, 'roc_logical_height': height,
            'roc_rotation': str(metadata['display_rotation']),
            'roc_panel_profile': str(MODEL_PROFILE[model])}


def main(args):
    constrained()
    require(not args.output.exists(), 'Fresh proof output required')
    args.output.mkdir(parents=True)
    controls = {str(path): sha(ordinary(path)) for path in (
        Path(__file__), Path(__file__).with_name('models.py'),
        ROOT / 'tools/boot_selector/reference_model.py', *PINNED)}
    for path, expected in PINNED.items():
        require(controls[str(path)] == expected, 'Frozen proof helper source changed: ' + str(path))
    spec = importlib.util.spec_from_file_location('roc_test8_frozen_final_execution', PROOF)
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    started = time.monotonic()
    result = {'schema': 'roc.test8.twelve-model-final-handoff.v1', 'passed': False,
              'controls': controls, 'cases': [], 'physical_device_accessed': False,
              'physical_card_accessed': False, 'ram_model_gate': False,
              'modeled_boundaries': ['environment API and runtime identity values', 'console',
                  'sunxi_flash/setenv/bootm leaf commands', 'hardware cleanup/cache API',
                  'zeroed bootm images/GD/BD and DRAM addresses',
                  'runtime architecture spare-header flag set to both zero and one'],
              'not_emulated': ['physical peripherals/DRAM/cache', 'ARM64 SMC trampoline',
                               'Linux/init/Android runtime or physical panels']}
    e = None
    try:
        candidate = ordinary(args.prefix)
        require(len(candidate) == PREFIX_BYTES and sha(candidate) == args.prefix_sha256,
                'Exact complete final prefix size and SHA required')
        toc_data = candidate[TOC_OFFSET:TOC_OFFSET + TOC_BYTES]
        toc = read_toc(toc_data)
        components = {}
        for name in ('u-boot', 'dtb', 'dtbo'):
            item = next(item for item in toc['items'] if item['name'] == name)
            components[name] = toc_data[item['offset']:item['offset'] + item['bytes']]
        blob, control_fdt, dtbo = (components[name] for name in ('u-boot', 'dtb', 'dtbo'))
        require(len(blob) == 0x100000 and len(dtbo) <= 0x10000, 'Exact executable/container size')
        boot = candidate[BOOT_OFFSET:BOOT_OFFSET + BOOT_BYTES]
        require(boot[:8] == b'ANDROID!' and struct.unpack_from('<II', boot, 36) == (2048, 2),
                'Android v2 boot header with 2048-byte pages')
        kernel_bytes, kernel_entry, initrd_size, initrd_start = struct.unpack_from('<IIII', boot, 8)
        sizes = [kernel_bytes, initrd_size, struct.unpack_from('<I', boot, 24)[0],
                 struct.unpack_from('<I', boot, 1648)[0]]
        offset, parts = 2048, {}
        for name, size in zip(('kernel', 'ramdisk', 'second', 'dtb'), sizes):
            parts[name] = {'offset': offset, 'bytes': size,
                           'sha256': sha(boot[offset:offset + size])}
            require(len(boot[offset:offset + size]) == size, 'Complete final boot component')
            offset += (size + 2047) & ~2047
        require(kernel_entry == 0x40080000 and initrd_start == 0x42000000 and initrd_size > 0,
                'Retained kernel and nonempty ramdisk load parameters')
        initrd_end = initrd_start + initrd_size
        loaded_offset, loaded_size = parts['dtb']['offset'], parts['dtb']['bytes']
        loaded = boot[loaded_offset:loaded_offset + loaded_size]
        require(struct.unpack_from('>II', loaded) == (0xd00dfeed, loaded_size),
                'Final loaded DTB complete header')
        loaded_address = 0x45000000 + loaded_offset
        environment = dict(decode_env(candidate[ENV_OFFSET:ENV_OFFSET + ENV_SIZE]))
        require(environment['roc_fdt_addr'] == 'fdt addr ${fdtcontroladdr}',
                'Actual final environment retains corrected runtime-control target')
        table = command_table(blob)
        result['inputs'] = {'prefix': str(args.prefix), 'prefix_sha256': args.prefix_sha256,
            'uboot_sha256': sha(blob), 'toc_sha256': sha(toc_data),
            'environment_sha256': sha(candidate[ENV_OFFSET:ENV_OFFSET + ENV_SIZE]),
            'boot_sha256': sha(boot), 'boot_components': parts,
            'kernel_entry': hex(kernel_entry), 'initrd_start': hex(initrd_start),
            'initrd_end': hex(initrd_end), 'loaded_fdt_address': hex(loaded_address)}
        result['reservations'] = []
        for slide in (0, 0x1000000):
            control, reservation = reserve_control(blob, table, control_fdt, dtbo, slide)
            result['reservations'].append(reservation)
            (args.output / ('runtime-control-' + str(slide) + '.dtb')).write_bytes(control)
            for model in ALL_MODEL_IDS:
                modes = ('controladdr', 'wrong-loaded-tight') if model == 'rg28xx' else ('controladdr',)
                for mode in modes:
                    route = 'selector'
                    env = dict(environment, **proof.RUNTIME, fdtcontroladdr=format(proof.CONTROL, 'x'),
                               roc_active_model=model, roc_boot_route=route)
                    if mode != 'controladdr':
                        env['roc_fdt_addr'] = 'fdt addr ' + format(loaded_address, 'x')
                    e = proof.FinalExecution(blob, table, env, loaded, slide)
                    # The final ramdisk can move the loaded DTB inside boot. Keep
                    # both the helper's old readback view and the actual address
                    # mapped, with no alias to runtime control or GD.
                    if loaded_address != proof.FDT_ADDRESS:
                        first = min(loaded_address & ~0xfff, proof.FDT_ADDRESS)
                        last = max((loaded_address + loaded_size + 0xfff) & ~0xfff,
                                   proof.FDT_ADDRESS + 0x30000)
                        require(last - first <= 0x100000 and last < proof.CONTROL,
                                'Bounded isolated loaded-FDT address window')
                        e.uc.mem_unmap(proof.FDT_ADDRESS, 0x30000)
                        e.uc.mem_map(first, last - first)
                        e.uc.mem_write(loaded_address, loaded)
                    e.uc.mem_map(proof.CONTROL, 0x30000)
                    e.uc.mem_write(proof.CONTROL, control)
                    e.uc.mem_write(proof.NEW_GD + 92, struct.pack('<I', proof.CONTROL))
                    e.uc.mem_write(proof.NEW_GD + 104, struct.pack('<I', len(control)))
                    images = e.base + 0xe7348
                    e.uc.mem_write(images, bytes(464))
                    proof.invoke(e, 0x64aac, (images + 144,))
                    e.uc.mem_write(images + 96, struct.pack('<I', kernel_entry))
                    execution = e.execute(env['bootcmd'])
                    require(execution['rc'] == 0 and execution['leaves'][-1]['command'] == 'bootm',
                            'Final parser/env reaches bootm')
                    working = word(e, e.base + 0x9d874)
                    require(working == (proof.CONTROL if mode == 'controladdr' else loaded_address),
                            'Actual working FDT pointer matches the tested tree')
                    first_rc = proof.invoke(e, 0xfda4, (working, initrd_start, initrd_end))
                    require(first_rc == (0 if mode == 'controladdr' else -3),
                            'Positive capacity or tight-loaded-tree negative reproduced')
                    require(proof.invoke(e, 0xf348, (0, 0, 0)) == 0, 'Actual bootm_find_images')
                    require(proof.invoke(e, 0x126d4, (images + 144, images + 108, images + 112)) == 0,
                            'Actual boot_relocate_fdt')
                    require(proof.invoke(e, 0x13fc, (images,)) == 0, 'Actual complete boot_prep_linux')
                    fdt_addr, fdt_len, rd_start, rd_end = struct.unpack(
                        '<IIII', e.uc.mem_read(images + 108, 16))
                    require(fdt_addr == proof.CONTROL and fdt_len == len(control) + 0x3000
                            and rd_start == rd_end == 0, 'Actual final control source/range')
                    source = bytes(e.uc.mem_read(proof.CONTROL, fdt_len))
                    handoffs = []
                    for flag in (0, 1):
                        e.uc.mem_write(e.base + 0x4e9, bytes([flag]))
                        jump = proof.invoke(e, 0x1470, (images, 0x400), handoff=True)
                        if flag:
                            require(jump['branch'] == 'arm64-trampoline' and jump['args'] == {
                                'r0': '0x8000ff04', 'r1': hex(kernel_entry),
                                'r2': hex(proof.DEST), 'r3': '0x1'}, 'ARM64 handoff arguments')
                        else:
                            require(jump['branch'] == 'arm32-entry' and jump['address'] == hex(kernel_entry)
                                    and jump['args']['r0'] == '0x0'
                                    and jump['args']['r1'] == '0xffffffff'
                                    and jump['args']['r2'] == hex(proof.DEST), 'ARM32 handoff arguments')
                        require(bytes(e.uc.mem_read(proof.DEST, fdt_len)) == source,
                                'Actual final memcpy complete byte equality')
                        handoffs.append(dict(jump, controlled_runtime_archflag=flag))
                    final = tree(e, proof.DEST)
                    expected_initrd = {'linux,initrd-start': initrd_start,
                                       'linux,initrd-end': initrd_end} if mode == 'controladdr' else {
                                           'linux,initrd-start': 0, 'linux,initrd-end': 0}
                    require(final['initrd'] == expected_initrd, 'Final initrd range survives correct tree only')
                    require(e.initrd_calls == [[working, initrd_start, initrd_end], [proof.CONTROL, 0, 0]],
                            'Actual initial valid and later zero-range initrd calls')
                    if mode == 'controladdr':
                        require(final['panel'] == dict(zip(PROPERTIES, VALUES[MODEL_PROFILE[model]])),
                                'All thirteen selected electrical cells survive actual handoff')
                    args_map = dict(token.split('=', 1) for token in final['bootargs'].split() if '=' in token)
                    for key, expected in expected_args(model, route).items():
                        require(args_map.get('androidboot.' + key) == expected,
                                'Final model feature bootarg mismatch: ' + model + ':' + key)
                    require(e.actual_counts['image_setup_libfdt'] == 1 and
                            e.actual_counts['boot_jump_linux'] == 2 and
                            e.actual_counts['memcpy'] >= 2 and e.actual_counts['is_arm64'] == 2,
                            'Required original continuation functions actually execute')
                    result['cases'].append({'slide': slide, 'model': model, 'mode': mode,
                        'first_initrd_rc': first_rc, 'final_DTB': final, 'final_copy_bytes': fdt_len,
                        'handoffs': handoffs, 'actual_functions': e.actual_counts,
                        'modeled_api_calls': e.modeled_calls, 'passed': True})
        require(all(sha(ordinary(Path(path))) == value for path, value in controls.items()),
                'Proof controls changed during execution')
        require(sha(ordinary(args.prefix)) == args.prefix_sha256, 'Final prefix changed during proof')
        result.update(passed=True, positive_cases=24, negative_cases=2, kernel_boundaries=52,
                      all12_final_timing_and_feature_args=True,
                      plus2025_reference_hardware_unverified=True,
                      physical_28xx_rotation_unverified=True)
    except Exception as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        if e is not None:
            result.update(last_pc=hex(e.uc.reg_read(e.a.UC_ARM_REG_PC)),
                          invalid_memory=e.invalid_memory, actual_functions=e.actual_counts)
    result['seconds'] = time.monotonic() - started
    receipt = json.dumps(result, ensure_ascii=False, indent=2).encode() + b'\n'
    (args.output / 'result.json').write_bytes(receipt)
    (args.output / 'result.sha256').write_text(sha(receipt) + '  result.json\n')
    print(json.dumps({key: result.get(key) for key in (
        'passed', 'positive_cases', 'negative_cases', 'kernel_boundaries', 'seconds', 'error')}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--prefix-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(main(parser.parse_args()))
