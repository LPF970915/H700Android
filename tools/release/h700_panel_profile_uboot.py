"""Read-only U-Boot profile consumer/bridge candidate; no image writer/build.

One image carries all four init tables. A separately guarded host selector
sets profile and all eleven timings in both FDTs before first use. This code
reads only the explicit profile; it does not infer identity from geometry,
old/boe, RAM, lid state or storage. There is no early timing rewrite.
"""
import hashlib
import json
import struct
import time
from collections import deque
from pathlib import Path

BASE = 0x4a000000
UBOOT_SHA = 'a11271e1276173cee48bd5705d068fd8446cfc0ffb43fca70b3b6808c2e9d0db'
BOE_ENTRY = 0x26424
OLD_ENTRY = 0x26b18
TAIL = 0x26afc
LIMIT = TAIL
TABLE_APPLY = 0x26b28
WORKING_FDT_CELL = 0x9d874
FDT_PATH_OFFSET = 0x67fdc
FDT_GETPROP = 0x67e7c
RELDYN_START = 0xe6450
RELDYN_END = 0xfdaa0
RELDYN_COUNT = 11978
RELDYN_SHA = 'e19623a7c601d7501d5edb167554c3c611d5871d939294d3f7c389d4fb8d3c7d'
RELOCATE_LOOP_START = 0x136c
RELOCATE_LOOP_END = 0x13d4
RELOCATE_LOOP_SHA = '80fdb86e0f28ffa6c3b818b96856c563def50273789d4711eb892f5b008d1f77'
RELOCATION_CELLS = (0x263f4, 0x2640c, 0x26414, 0x26418, 0x2641c,
                    0x26420, 0x26b10, 0x26b14, 0x27a04)
PATH = '/soc@03000000/lcd0@01c0c000'
PROPERTY = 'roc_panel_profile'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def guard_original(blob):
    require(len(blob) == 1048576, 'Pinned U-Boot byte count')
    require(hashlib.sha256(blob).hexdigest() == UBOOT_SHA, 'Pinned U-Boot SHA256')
    require(blob[0x262e4:0x262e6] == bytes.fromhex('38b5'), 'Native init 16-byte frame')
    require(blob[0x263e8:0x263ec] == bytes.fromhex('2568012d'), 'Native r5 old/boe branch')
    require(blob[TAIL:TAIL+4] == bytes.fromhex('2368002b'), 'Original env tail r4 dereference')
    require(struct.unpack_from('<I', blob, 0x868c)[0] == BASE + WORKING_FDT_CELL,
            'Actual set_working_fdt_addr global cell')
    require(struct.unpack_from('<I', blob, 0x209d4)[0] == BASE + WORKING_FDT_CELL,
            'Actual display property reader global cell')
    require(all(not (BOE_ENTRY <= n < LIMIT) for n in RELOCATION_CELLS),
            'Payload overlaps a native relocation cell')
    return {'bridge_start': BOE_ENTRY, 'bridge_limit': LIMIT,
            'capacity': LIMIT - BOE_ENTRY, 'old_entry_redirect': OLD_ENTRY,
            'tail': TAIL, 'table_apply': TABLE_APPLY,
            'working_fdt_cell': WORKING_FDT_CELL,
            'fdt_path_offset': FDT_PATH_OFFSET, 'fdt_getprop': FDT_GETPROP,
            'no_drv_disp_init_or_timing_patch': True}


def assembly():
    return f'''.syntax unified
.thumb
.section .text.roc_panel_init_bridge,"ax",%progbits
.p2align 2
.global roc_panel_init_bridge
.type roc_panel_init_bridge,%function
.thumb_func
roc_panel_init_bridge:
    bl roc_profile_read_uboot
    mov r1,r5
    bl roc_table_apply
    b.w roc_panel_init_tail
.size roc_panel_init_bridge,.-roc_panel_init_bridge

.section .text.roc_profile_read_uboot,"ax",%progbits
.p2align 2
.global roc_profile_read_uboot
.type roc_profile_read_uboot,%function
.thumb_func
roc_profile_read_uboot:
    push {{r4,lr}}
    sub sp,#8
    adr.w r0,.Lworking_fdt_delta
    ldr r1,[r0]
    add r0,r0,r1
    ldr r4,[r0]
    cbz r4,.Lprofile_zero
    adr.w r1,.Lpanel_path
    mov r0,r4
    bl roc_fdt_path_offset
    cmp r0,#0
    blt .Lprofile_zero
    mov r1,r0
    mov r0,r4
    adr.w r2,.Lprofile_name
    movs r3,#0
    str r3,[sp]
    mov r3,sp
    bl roc_fdt_getprop
    cbz r0,.Lprofile_zero
    ldr r1,[sp]
    cmp r1,#4
    bne .Lprofile_zero
    ldr r0,[r0]
    rev r0,r0
    cmp r0,#1
    bne .Lprofile_zero
    movs r0,#1
    b .Lprofile_done
.Lprofile_zero:
    movs r0,#0
.Lprofile_done:
    add sp,#8
    pop {{r4,pc}}
.p2align 2
.Lworking_fdt_delta:
    .word 0x{BASE + WORKING_FDT_CELL:x} - .Lworking_fdt_delta
.Lpanel_path:
    .asciz "{PATH}"
.Lprofile_name:
    .asciz "{PROPERTY}"
.size roc_profile_read_uboot,.-roc_profile_read_uboot

.global roc_fdt_path_offset
.type roc_fdt_path_offset,%function
.thumb_set roc_fdt_path_offset,0x{BASE + FDT_PATH_OFFSET + 1:x}
.global roc_fdt_getprop
.type roc_fdt_getprop,%function
.thumb_set roc_fdt_getprop,0x{BASE + FDT_GETPROP + 1:x}
.global roc_table_apply
.type roc_table_apply,%function
.thumb_set roc_table_apply,0x{BASE + TABLE_APPLY + 1:x}
.global roc_panel_init_tail
.type roc_panel_init_tail,%function
.thumb_set roc_panel_init_tail,0x{BASE + TAIL + 1:x}
.section .note.GNU-stack,"",%progbits
'''


def linker():
    return f'''ENTRY(roc_panel_init_bridge)
SECTIONS {{
 .payload 0x{BASE + BOE_ENTRY:x} : {{
   *(.text.roc_panel_init_bridge) *(.text*) *(.rodata*)
 }}
 /DISCARD/ : {{ *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }}
 ASSERT(ADDR(.payload)+SIZEOF(.payload) <= 0x{BASE + LIMIT:x}, "profile reader payload limit")
}}
'''


def _relocate_original_for_emulator(original, payload_length, slide):
    """Reproduce only the pinned original ARM R_ARM_RELATIVE loop in RAM.

    The actual loop at 0x136c computes r4=runtime_base-original_base and
    iterates the bounds loaded from 0x13cc/0x13d0. For type23 it adds r4
    both to the target address and to the original word at that target.
    Its separate ARM-state instructions and literals are hash guarded;
    no old-address mapping or instruction-hook substitution is used.
    """
    guard_original(original)
    require(slide in (0, 0x01000000), 'Declared emulator relocation slides')
    require(0 < payload_length <= LIMIT - BOE_ENTRY,
            'Relocation protected payload bounds')
    require(hashlib.sha256(original[RELOCATE_LOOP_START:RELOCATE_LOOP_END]).hexdigest()
            == RELOCATE_LOOP_SHA, 'Actual ARM relocation loop SHA256')
    require(struct.unpack_from('<III', original, 0x13c8)
            == (BASE + RELDYN_START, BASE + RELDYN_START, BASE + RELDYN_END),
            'Actual copy-end and relocation start/end literals')
    region = original[RELDYN_START:RELDYN_END]
    require(len(region) == RELDYN_COUNT * 8 and
            hashlib.sha256(region).hexdigest() == RELDYN_SHA,
            'Pinned actual .rel.dyn extent/count/SHA256')
    relocated = bytearray(original)
    targets = []
    for target, info in struct.iter_unpack('<II', region):
        require(info == 23, 'Only original R_ARM_RELATIVE records are supported')
        offset = target - BASE
        require(0 <= offset <= len(original) - 4 and offset % 4 == 0,
                'Original relocation target bounds/alignment')
        require(not targets or offset > targets[-1],
                'Original relocation targets must be ordered and unique')
        require(not (offset < BOE_ENTRY + payload_length and offset + 4 > BOE_ENTRY),
                'Original relocation overlaps injected dispatcher payload')
        require(not (offset < RELDYN_END and offset + 4 > RELDYN_START),
                'Original relocation modifies its own table')
        value = struct.unpack_from('<I', original, offset)[0]
        require(value + slide <= 0xffffffff, 'Original relocation word overflow')
        if slide:
            struct.pack_into('<I', relocated, offset, value + slide)
        targets.append(offset)
    require(len(targets) == RELDYN_COUNT, 'Actual relocation record count')
    # This libfdt absolute jump table caused the unrelocated negative control.
    require(0x66c5c in targets and
            struct.unpack_from('<I', relocated, 0x66c5c)[0]
            == struct.unpack_from('<I', original, 0x66c5c)[0] + slide,
            'Actual libfdt jump-table relocation')
    return bytes(relocated), {
        'original_sha256': UBOOT_SHA,
        'actual_loop_sha256': RELOCATE_LOOP_SHA,
        'table_start': RELDYN_START, 'table_end': RELDYN_END,
        'table_sha256': RELDYN_SHA, 'record_type': 'R_ARM_RELATIVE',
        'records_validated': len(targets),
        'records_applied': len(targets) if slide else 0,
        'slide': slide, 'target_min': min(targets), 'target_max': max(targets),
        'dispatcher_overlap': False, 'original_address_alias_mapped': False,
        'emulator_memory_only': True,
    }


def execute_actual_reader(original, payload, reader_offset, fdt_blob,
                          expected_profile, *, slide=0, null_fdt=False,
                          instruction_limit=2_000_000, timeout_us=10_000_000,
                          diagnostic_path=None):
    """Execute final emitted reader plus original libfdt/strlen instructions.

    This function never starts a compiler or changes an on-disk image. Root's
    integrating verifier supplies final emitted payload/symbol and test FDT.
    Final code execution must still verify the bridge and command streams.
    """
    guard_original(original)
    require(BOE_ENTRY <= reader_offset < BOE_ENTRY + len(payload) <= LIMIT,
            'Reader/final payload bounds')
    require(slide in (0, 0x01000000), 'Declared emulator relocation slides')
    require(100_000 <= instruction_limit <= 5_000_000,
            'Bounded real-libfdt instruction budget')
    require(0 < timeout_us <= 10_000_000, 'Bounded real-libfdt execution timeout')
    if diagnostic_path is not None:
        diagnostic_path = Path(diagnostic_path)
        require(not diagnostic_path.exists(), 'Preserve previous reader diagnostics')
    import unicorn as uc
    from unicorn import arm_const as ar
    require(uc.__version__ == '2.1.4', 'Pinned isolated Unicorn2.1.4')
    base = BASE + slide
    stack, stack_size = 0x42000000, 0x10000
    fdt_addr, return_addr, gd = 0x48000000, 0x41000000, 0x44000000
    fdt_size = max(0x1000, (len(fdt_blob) + 0xfff) & ~0xfff)
    cpu = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_THUMB)
    for address, size in [(base, 0x100000), (stack, stack_size),
                          (fdt_addr, fdt_size), (return_addr, 0x1000), (gd, 0x1000)]:
        cpu.mem_map(address, size)
    relocated_original, relocation = _relocate_original_for_emulator(
        original, len(payload), slide)
    cpu.mem_write(base, relocated_original)
    cpu.mem_write(base + BOE_ENTRY, bytes(payload))
    cpu.mem_write(fdt_addr, bytes(fdt_blob))
    cpu.mem_write(base + WORKING_FDT_CELL, struct.pack('<I', 0 if null_fdt else fdt_addr))
    registers = [ar.UC_ARM_REG_R4, ar.UC_ARM_REG_R5, ar.UC_ARM_REG_R6,
                 ar.UC_ARM_REG_R7, ar.UC_ARM_REG_R8, ar.UC_ARM_REG_R9,
                 ar.UC_ARM_REG_R10, ar.UC_ARM_REG_R11]
    saved = {r: 0x5a000000 + i*0x1111 for i, r in enumerate(registers)}
    saved[ar.UC_ARM_REG_R9] = gd
    for reg, value in saved.items():
        cpu.reg_write(reg, value)
    initial_sp = stack + stack_size - 0x100
    cpu.reg_write(ar.UC_ARM_REG_SP, initial_sp)
    cpu.reg_write(ar.UC_ARM_REG_LR, return_addr | 1)
    returned, calls, last_pcs = [], [], deque(maxlen=32)
    instruction_count = 0

    def hook(machine, address, size, user):
        nonlocal instruction_count
        instruction_count += 1
        last_pcs.append(hex(address))
        if address == return_addr:
            returned.append(True)
            machine.emu_stop()
            return
        offset = address - base
        require(BOE_ENTRY <= offset < BOE_ENTRY + len(payload) or
                0x66b00 <= offset < 0x68300 or 0x69800 <= offset < 0x69b00,
                'Unexpected executed instruction: ' + hex(offset))
        if offset in (FDT_PATH_OFFSET, FDT_GETPROP):
            require(machine.reg_read(ar.UC_ARM_REG_R9) == gd, 'r9/gd changed')
            require(machine.reg_read(ar.UC_ARM_REG_SP) % 8 == 0, 'Helper stack alignment')
            calls.append(offset)

    cpu.hook_add(uc.UC_HOOK_CODE, hook)
    error = None
    started = time.monotonic()
    try:
        cpu.emu_start((base + reader_offset) | 1, base + 0x100000,
                      timeout=timeout_us, count=instruction_limit)
    except Exception as caught:
        error = caught
    elapsed = time.monotonic() - started
    final_sp = cpu.reg_read(ar.UC_ARM_REG_SP)
    diagnostic = {
        'relocation': relocation,
        'instruction_count': instruction_count, 'instruction_limit': instruction_limit,
        'timeout_us': timeout_us, 'elapsed_seconds': round(elapsed, 6),
        'returned': returned == [True],
        'stop_reason': ('returned' if returned == [True] else
                        'emulation_error' if error is not None else
                        'instruction_budget' if instruction_count >= instruction_limit else
                        'bounded_stop_without_return'),
        'final_PC': hex(cpu.reg_read(ar.UC_ARM_REG_PC)),
        'final_LR': hex(cpu.reg_read(ar.UC_ARM_REG_LR)),
        'initial_SP': hex(initial_sp), 'final_SP': hex(final_sp),
        'final_r0_r1_r2_r3': [hex(cpu.reg_read(reg)) for reg in
                            [ar.UC_ARM_REG_R0, ar.UC_ARM_REG_R1,
                             ar.UC_ARM_REG_R2, ar.UC_ARM_REG_R3]],
        'last_32_PCs': list(last_pcs), 'helper_calls': list(map(hex, calls)),
        'stack_64bytes_hex': (bytes(cpu.mem_read(final_sp, 64)).hex()
                             if stack <= final_sp <= stack + stack_size - 64 else None),
        'error': None if error is None else repr(error),
    }
    if diagnostic_path is not None:
        diagnostic_path.write_text(json.dumps(diagnostic, indent=2)+'\n')
    require(error is None, 'Actual reader execution failed: '+json.dumps(diagnostic))
    require(returned == [True], 'Reader did not return: '+json.dumps(diagnostic))
    require(cpu.reg_read(ar.UC_ARM_REG_R0) == expected_profile, 'Unexpected selected profile')
    require(cpu.reg_read(ar.UC_ARM_REG_SP) == initial_sp, 'Reader stack not restored')
    require(all(cpu.reg_read(r) == value for r, value in saved.items()), 'Reader callee-saved register changed')
    require(bytes(cpu.mem_read(fdt_addr, len(fdt_blob))) == bytes(fdt_blob), 'Reader modified FDT')
    return {'slide': slide, 'profile': expected_profile, 'null_fdt': null_fdt,
            'actual_libfdt_executed': True, 'read_only_fdt': True,
            'SP_callee_saved_r9': True, 'helper_calls': list(map(hex, calls)),
            'execution': diagnostic}
