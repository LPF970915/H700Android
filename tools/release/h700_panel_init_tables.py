"""Compile/execute an ordinary-file H700 four-table library, never an image.

This library needs an external trustworthy profile selector before integration.
It does not identify a board/panel, edit an image, select DTB timings or alter
any original driver.  Unknown profiles reproduce the retained720 event stream;
that fallback is not a claim of displaying on unknown hardware.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import shutil
import stat
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
from package_h700_v6a import constrained

AUDIT = REPO / 'out/rg34xx-boot-analysis-20261114/rg35xxh-reference-init-audit.json'
AUDIT_SHA = '2eb9cf9b17f89264e4cb72a2af1143088a3173087bcc3fefe22743221e773420'
REFERENCE_SHA = '867700c6278bdcc70b3a335669f34f03c2cca1f240cd043be00310572551561d'
C_SOURCE = Path(__file__).with_suffix('.c')
CLANG = Path('/home/lpf/h700-android10/android/prebuilts/clang/host/linux-x86/clang-r353983c/bin')
OP = {'COMMAND': 1, 'DATA': 2, 'WAIT_MS': 3}
# SHA256 of actual event opcode/value bytes, without the uint16 count header.
STREAM_LOCK = {
 'uboot720_old': (635, '439028cffe754a457776b5edb0042f51977ce322206553174061e719b9a50100'),
 'kernel720_old': (636, '6d061ac1122ebc53bc4720cb22c11061310063314e72ce5f97095bc36921acaf'),
 '720_boe': (292, 'e790b5cafe78a02f106e01d3718057a1e064f60c59ccd16b49d32417ee641679'),
 '640_old': (386, '78ab4093b108507e4a16a7b6fe965e382e5eeed279b8ef978c90ce82c986041b'),
 '640_boe': (294, '7aa865b1076bddf001dd82c2681669d8ff84f3c06e3b8310e4072af35de24bb7'),
}
ARCH = {
 'uboot': {'base': 0x4a000000, 'payload': 0x26b28, 'limit': 0x27a04,
            'command': 0x27e3c, 'data': 0x27fcc, 'delay': 0x2621c,
            'bits': 32, 'machine': 40, 'target': 'armv7a-none-eabi',
            'objdump': '/usr/bin/arm-linux-gnueabihf-objdump'},
 'kernel': {'base': 0xffffff8008080000, 'payload': 0x3a3480, 'limit': 0x3a482c,
             'command': 0x3a1f18, 'data': 0x3a247c, 'delay': 0x39a2d8,
             'bits': 64, 'machine': 183, 'target': 'aarch64-none-elf',
             'objdump': '/usr/bin/aarch64-linux-gnu-objdump'},
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def regular(path):
    require(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), 'Ordinary file required: '+str(path))
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def packed(rows):
    return bytes(value for kind, byte in rows for value in (OP[kind], byte))


def load_tables():
    raw = regular(AUDIT).read_bytes()
    require(sha(raw) == AUDIT_SHA, 'Full trace audit identity changed')
    audit = json.loads(raw)
    current = next(row for row in audit['uboot'] if row['name'] == 'current_rg34xxsp')
    reference = next(row for row in audit['uboot'] if row['name'] == 'reference_rg35xxh')
    require(reference['sha256'] == audit['reference']['u_boot_sha256'] == REFERENCE_SHA,
            'Pinned RG35XXH primary reference identity changed')
    tables = {}
    for arch in ARCH:
        legacy = current if arch == 'uboot' else audit['current_kernel']
        values = {}
        for profile, source in [('legacy', legacy), ('rg35h', reference)]:
            for branch in ['old', 'boe']:
                trace = source['branches'][branch]
                rows = [(r['kind'], r['value']) for r in trace['events']]
                require(all(kind in OP and 0 <= byte <= 255 for kind, byte in rows), 'Unsupported event')
                key = (arch+'720_old' if branch == 'old' else '720_boe') if profile == 'legacy' else '640_'+branch
                count, digest = STREAM_LOCK[key]
                require(len(rows) == trace['event_count'] == count and sha(packed(rows)) == digest,
                        'Complete event stream mismatch: '+arch+'/'+profile+'/'+branch)
                values[profile+'_'+branch] = rows
        tables[arch] = values
    require(tables['kernel']['legacy_old'] == tables['uboot']['legacy_old']+[('WAIT_MS',100)],
            'Original architecture-specific final100ms must remain distinct')
    return tables


def assembly(arch, profile, tables):
    thumb = arch == 'uboot'
    lines = ['.syntax unified', '.thumb'] if thumb else []
    lines += ['.section .text.panel_table,"ax",%progbits', '.p2align 2',
              '.global panel_table', '.type panel_table,%function']
    if thumb:
        lines += ['.thumb_func', 'panel_table:', 'cmp r0,#1', 'beq 2f',
                  'cmp r1,#1', 'beq 1f', 'adr.w r0,table_legacy_old', 'bx lr',
                  '1:', 'adr.w r0,table_legacy_boe', 'bx lr',
                  '2:', 'cmp r1,#1', 'beq 3f', 'adr.w r0,table_rg35h_old', 'bx lr',
                  '3:', 'adr.w r0,table_rg35h_boe', 'bx lr']
    else:
        lines += ['panel_table:', 'cmp w0,#1', 'b.eq 2f',
                  'cmp w1,#1', 'b.eq 1f', 'adr x0,table_legacy_old', 'ret',
                  '1:', 'adr x0,table_legacy_boe', 'ret',
                  '2:', 'cmp w1,#1', 'b.eq 3f', 'adr x0,table_rg35h_old', 'ret',
                  '3:', 'adr x0,table_rg35h_boe', 'ret']
    lines += ['.size panel_table,.-panel_table', '.p2align 1']
    for name, rows in tables.items():
        lines += [f'.global table_{name}', f'.type table_{name},%object',
                  f'table_{name}:', f'.hword {len(rows)}']
        lines += [f'.byte {OP[kind]},{value}' for kind, value in rows]
        lines += [f'.size table_{name},.-table_{name}']
    # Thumb-marked absolute linker symbols generate relative BL, not BLX.
    # They are not function pointers stored in the payload.
    for symbol, key in [('panel_cmd','command'), ('panel_data','data'), ('panel_wait','delay')]:
        value = profile['base']+profile[key]+int(thumb)
        lines += [f'.global {symbol}', f'.type {symbol},%function',
                  f'.thumb_set {symbol},0x{value:x}' if thumb else f'.set {symbol},0x{value:x}']
    lines += ['.section .note.GNU-stack,"",%progbits', '']
    return '\n'.join(lines)


def linker(profile):
    address = profile['base']+profile['payload']
    limit = profile['base']+profile['limit']
    return f'''ENTRY(panel_apply)
SECTIONS {{
 .payload 0x{address:x} : {{ *(.text.panel_apply) *(.text*) *(.rodata*) }}
 /DISCARD/ : {{ *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }}
 ASSERT(ADDR(.payload)+SIZEOF(.payload) <= 0x{limit:x}, "library payload limit")
}}
'''


def read_elf(raw, profile):
    """Strict ELF reader independent of compiler output listing/symbol tools."""
    bits = profile['bits']
    require(raw[:7] == b'\x7fELF'+bytes([1 if bits == 32 else 2,1,1]), 'ELF encoding')
    require(struct.unpack_from('<HH',raw,16) == (2,profile['machine']), 'ELF type/machine')
    if bits == 32:
        shoff, = struct.unpack_from('<I',raw,32)
        entsize,count,names = struct.unpack_from('<HHH',raw,46)
        fmt = '<10I'
    else:
        shoff, = struct.unpack_from('<Q',raw,40)
        entsize,count,names = struct.unpack_from('<HHH',raw,58)
        fmt = '<II4QII2Q'
    require(entsize == struct.calcsize(fmt), 'Section header size')
    headers = [struct.unpack_from(fmt,raw,shoff+i*entsize) for i in range(count)]
    nh = headers[names]
    section_names = raw[nh[4]:nh[4]+nh[5]]
    sections,symbols = [],{}
    for h in headers:
        end = section_names.find(b'\0',h[0])
        require(end >= h[0], 'Section name bounds')
        name = section_names[h[0]:end].decode('ascii')
        require(not (h[1] in (4,9) and h[5]), 'Unresolved relocation section')
        if h[2]&2 and h[5]:
            require(h[1] == 1 and name == '.payload', 'Unexpected allocated section')
            data = raw[h[4]:h[4]+h[5]]
            require(len(data) == h[5], 'Truncated section')
            sections.append({'name':name,'offset':h[3]-profile['base'],'bytes':data,
                             'header_offset':shoff+headers.index(h)*entsize})
        if h[1] == 2:
            linked = headers[h[6]]
            strings = raw[linked[4]:linked[4]+linked[5]]
            require(h[9] == (16 if bits == 32 else 24), 'Symbol entry size')
            for position in range(h[4],h[4]+h[5],h[9]):
                if bits == 32:
                    n,value,size,info,other,index = struct.unpack_from('<IIIBBH',raw,position)
                else:
                    n,info,other,index,value,size = struct.unpack_from('<IBBHQQ',raw,position)
                end = strings.find(b'\0',n)
                require(end >= n, 'Symbol name bounds')
                key = strings[n:end].decode('ascii')
                if key:
                    require(key not in symbols or key.startswith('$'), 'Duplicate symbol')
                    symbols[key] = {'value':value,'bytes':size,'type':info&15,'index':index}
    validate_sections(sections,profile)
    for key in ['panel_apply','panel_table']+[ 'table_'+name for name in
                    ['legacy_old','legacy_boe','rg35h_old','rg35h_boe']]:
        require(key in symbols, 'Missing symbol: '+key)
        value = symbols[key]['value']&~1 if key.startswith('panel_') and bits == 32 else symbols[key]['value']
        require(profile['payload'] <= value-profile['base'] < profile['limit'], 'Symbol out of payload')
    return sections[0],symbols


def validate_sections(sections,profile):
    require(len(sections)==1 and sections[0]['name']=='.payload', 'Library section set')
    row=sections[0]
    require(row['offset']==profile['payload'] and 0 < len(row['bytes']) <= profile['limit']-row['offset'],
            'Library payload outside approved bounds')


def expected(tables,profile,branch):
    return tables[('rg35h' if profile==1 else 'legacy')+('_boe' if branch==1 else '_old')]


def execute(arch,p,payload,symbols,tables,profile,branch,slide=0):
    """Execute emitted final bytes, reject any undeclared code entry or helper.

    No original image is mapped or read. Helper hooks exercise real relative BL
    targets, signed-byte ABI, stack alignment, r9/gd and caller-clobber behavior.
    """
    import unicorn as uc
    from unicorn import arm_const as ar, arm64_const as aa
    require(uc.__version__=='2.1.4','Pinned Unicorn2.1.4 required')
    thumb=arch=='uboot'
    base=(p['base'] if thumb else 0x08080000)+slide
    cpu=uc.Uc(uc.UC_ARCH_ARM if thumb else uc.UC_ARCH_ARM64,
              uc.UC_MODE_THUMB if thumb else uc.UC_MODE_ARM)
    mapped=(p['limit']+4095)&~4095
    cpu.mem_map(base,mapped,uc.UC_PROT_READ|uc.UC_PROT_EXEC)
    cpu.mem_write(base+p['payload'],payload)
    cpu.mem_map(0x70000000,0x10000)
    registers=({i:getattr(ar,'UC_ARM_REG_R'+str(i)) for i in range(13)} if thumb else
               {i:getattr(aa,'UC_ARM64_REG_X'+str(i)) for i in range(31)})
    spreg=ar.UC_ARM_REG_SP if thumb else aa.UC_ARM64_REG_SP
    pcreg=ar.UC_ARM_REG_PC if thumb else aa.UC_ARM64_REG_PC
    lrreg=ar.UC_ARM_REG_LR if thumb else aa.UC_ARM64_REG_LR
    preserved=list(range(4,12)) if thumb else list(range(19,30))
    for i in preserved:
        cpu.reg_write(registers[i],0x12340000+i*0x100)
    saved={i:cpu.reg_read(registers[i]) for i in preserved}
    initial_sp=0x7000ff00
    cpu.reg_write(spreg,initial_sp)
    cpu.reg_write(registers[0],profile)
    cpu.reg_write(registers[1],branch)
    return_to=base+0x1000
    cpu.reg_write(lrreg,return_to+int(thumb))
    wanted=expected(tables,profile,branch)
    helpers={p['command']:'COMMAND',p['data']:'DATA',p['delay']:'WAIT_MS'}
    captured,calls,offsets,returned=[],[],[],[]

    def hook(machine,address,size,unused):
        offset=address-base
        offsets.append(offset)
        if address==return_to:
            returned.append(True)
            machine.emu_stop()
            return
        if offset in helpers:
            kind=helpers[offset]
            raw=machine.reg_read(registers[0])
            value=raw&255
            if kind=='WAIT_MS' or thumb:
                require(raw==value,'Unsigned helper argument ABI')
            else:
                signed32=value if value<128 else 0x100000000+value-256
                require(raw==signed32,'A64 signed-char w0 ABI')
            require(machine.reg_read(spreg)%(8 if thumb else 16)==0,'Helper stack alignment')
            if thumb:
                require(machine.reg_read(registers[9])==saved[9],'U-Boot gd/r9 changed at helper call')
            captured.append((kind,value))
            require(len(captured)<=len(wanted) and captured[-1]==wanted[len(captured)-1],
                    'Executed event differs from locked reference')
            lr=machine.reg_read(lrreg)
            calls.append({'kind':kind,'value':value,'raw_argument':raw,'target_offset':offset,
                          'call_offset':(lr&~1)-base-4})
            for i in ([0,1,2,3,12] if thumb else list(range(18))):
                machine.reg_write(registers[i],0x55aa0000+i)
            if thumb:
                machine.reg_write(ar.UC_ARM_REG_APSR_NZCV,0xa0000000)
            else:
                machine.reg_write(aa.UC_ARM64_REG_NZCV,0xa0000000)
            machine.reg_write(pcreg,lr)
            return
        require(p['payload']<=offset<p['payload']+len(payload),
                'Executed outside library or declared helper: '+hex(offset))

    cpu.hook_add(uc.UC_HOOK_CODE,hook)
    entry=(symbols['panel_apply']['value']&~1)-p['base']
    cpu.emu_start(base+entry+int(thumb),base+mapped,timeout=10_000_000,count=100_000)
    require(returned==[True] and captured==wanted,'Missing return or incomplete event stream')
    require(cpu.reg_read(spreg)==initial_sp,'Stack not restored')
    require(all(cpu.reg_read(registers[i])==value for i,value in saved.items()),'Callee-saved register changed')
    return {'profile':profile,'branch':branch,'slide':slide,'events':len(captured),
            'event_sha256':sha(packed(captured)),'instructions':len(offsets),
            'exact_reference':True,'helper_ABI':True,'r9_gd_at_every_helper':thumb,
            'callee_saved_and_SP_preserved':True,'returned':True,
            'calls':calls,'executed_offsets':sorted(set(offsets))}


def reject(label,callback):
    try:
        callback()
    except (ValueError,RuntimeError):
        return {'case':label,'rejected':True}
    raise ValueError('Negative control accepted: '+label)


def relative_branch(arch,pc,target,call):
    if arch=='kernel':
        distance=target-pc
        require(distance%4==0 and -(1<<27)<=distance<(1<<27),'A64 branch range')
        return struct.pack('<I',(0x94000000 if call else 0x14000000)|((distance>>2)&0x3ffffff))
    distance=target-(pc+4)
    require(distance%2==0 and -(1<<24)<=distance<(1<<24),'Thumb branch range')
    s=(distance>>24)&1
    i1,i2=(distance>>23)&1,(distance>>22)&1
    j1,j2=(~i1^s)&1,(~i2^s)&1
    first=0xf000|(s<<10)|((distance>>12)&0x3ff)
    second=(0xd000 if call else 0x9000)|(j1<<13)|(j2<<11)|((distance>>1)&0x7ff)
    return struct.pack('<HH',first,second)


def build(work,output):
    require(not work.exists() and not output.exists(),'Fresh work/output required; preserve failures')
    tables=load_tables()
    import unicorn
    require(unicorn.__version__=='2.1.4','Use isolated Python with unicorn==2.1.4')
    controls={str(path.relative_to(REPO)):sha(regular(path).read_bytes()) for path in [Path(__file__),C_SOURCE,AUDIT]}
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    report={'passed':False,'scope':'host-only four-table compiled library; no profile detection or image integration',
            'automatic_identity_implemented':False,'image_created_or_modified':False,'device_card_written':False,
            'unknown_profile':'exact retained720 events; unknown hardware display not accepted',
            'profile0':'retained720','profile1':'pinned RG35XXH640','branch1':'boe','other_branch':'old',
            'audit_sha256':AUDIT_SHA,'reference_sha256':REFERENCE_SHA,'controls':controls,
            'unicorn':unicorn.__version__,'profiles':{},'negative_controls':[]}
    write_json(output/'result.json',report)
    try:
        for arch,p in ARCH.items():
            print('PHASE=compile_four_tables_'+arch,flush=True)
            stage=work/arch
            stage.mkdir()
            (stage/'panel.S').write_text(assembly(arch,p,tables[arch]),encoding='ascii')
            (stage/'panel.ld').write_text(linker(p),encoding='ascii')
            shutil.copyfile(C_SOURCE,stage/'panel.c')
            flags=['--target='+p['target'],'-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector',
                   '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-jump-tables',
                   '-ffunction-sections','-fdata-sections','-fno-pic','-fno-pie','-Wall','-Wextra','-Werror']
            flags+=(['-mthumb','-march=armv7-a','-mfloat-abi=soft','-ffixed-r9'] if arch=='uboot' else
                    ['-march=armv8-a','-mgeneral-regs-only','-ffixed-x18','-DPANEL_SIGNED_BYTE'])
            commands=[
                [str(CLANG/'clang.real')]+flags+['-c','panel.c','-o','panel.o'],
                [str(CLANG/'clang.real'),'--target='+p['target']]+
                (['-mthumb','-march=armv7-a'] if arch=='uboot' else ['-march=armv8-a'])+
                ['-c','panel.S','-o','table.o'],
                [str(CLANG/'ld.lld'),'-T','panel.ld','-e','panel_apply','--no-undefined','--fatal-warnings',
                 '--build-id=none','-Map=panel.map','-o','panel.elf','panel.o','table.o'],
            ]
            for command in commands:
                subprocess.run(command,cwd=stage,check=True)
            raw=(stage/'panel.elf').read_bytes()
            section,symbols=read_elf(raw,p)
            payload=section['bytes']
            for name,rows in tables[arch].items():
                offset=symbols['table_'+name]['value']-p['base']-p['payload']
                actual=payload[offset:offset+2+len(rows)*2]
                require(actual==struct.pack('<H',len(rows))+packed(rows),'Final linked table bytes changed')
            listing=subprocess.check_output([p['objdump'],'-d',str(stage/'panel.elf')],text=True)
            (stage/'panel.disassembly.txt').write_text(listing,encoding='ascii')
            (output/(arch+'.library.bin')).write_bytes(payload)
            shutil.copyfile(stage/'panel.elf',output/(arch+'.library.elf'))
            print('PHASE=execute_final_bytes_'+arch,flush=True)
            runs=[execute(arch,p,payload,symbols,tables[arch],profile,branch,slide)
                  for slide in [0,0x02000000] for profile in [0,1,2,0xffffffff] for branch in [0,1,2]]
            negatives=report['negative_controls']
            bad=copy.deepcopy(section);bad['offset']+=4
            negatives += [reject(arch+'_section_offset',lambda:validate_sections([bad],p))]
            bad=copy.deepcopy(section);bad['bytes']+=bytes(p['limit']-p['payload']+1)
            negatives += [reject(arch+'_payload_overrun',lambda:validate_sections([bad],p))]
            badelf=bytearray(raw)
            struct.pack_into('<I',badelf,section['header_offset']+4,4)
            negatives += [reject(arch+'_unresolved_relocation',lambda:read_elf(bytes(badelf),p))]
            index=symbols['table_legacy_old']['value']-p['base']-p['payload']
            corrupt=bytearray(payload);corrupt[index+3]^=1
            negatives += [reject(arch+'_actual_event_byte_corrupted',
                lambda:execute(arch,p,bytes(corrupt),symbols,tables[arch],0,0))]
            corrupt=bytearray(payload);struct.pack_into('<H',corrupt,index,637)
            negatives += [reject(arch+'_count_exceeds_fixed_limit',
                lambda:execute(arch,p,bytes(corrupt),symbols,tables[arch],0,0))]
            corrupt=bytearray(payload);corrupt[index+2]=0xff
            negatives += [reject(arch+'_invalid_event_opcode',
                lambda:execute(arch,p,bytes(corrupt),symbols,tables[arch],0,0))]
            call=runs[0]['calls'][0]['call_offset']
            corrupt=bytearray(payload)
            corrupt[call-p['payload']:call-p['payload']+4]=relative_branch(arch,call,p['command']+4,True)
            negatives += [reject(arch+'_actual_call_to_undeclared_helper',
                lambda:execute(arch,p,bytes(corrupt),symbols,tables[arch],0,0))]
            entry=(symbols['panel_apply']['value']&~1)-p['base']
            corrupt=bytearray(payload)
            corrupt[entry-p['payload']:entry-p['payload']+4]=relative_branch(arch,entry,p['payload']-32,False)
            negatives += [reject(arch+'_actual_branch_outside_library',
                lambda:execute(arch,p,bytes(corrupt),symbols,tables[arch],0,0))]
            detail={'arch':arch,'bytes':len(payload),'payload_sha256':sha(payload),'elf_sha256':sha(raw),
                    'payload_offset':p['payload'],'end_exclusive':p['payload']+len(payload),'maximum_end':p['limit'],
                    'no_relocations':True,'no_original_image_read_or_write':True,
                    'tables':{name:{'count':len(rows),'event_sha256':sha(packed(rows)),
                                    'wait_ms':[value for kind,value in rows if kind=='WAIT_MS']}
                              for name,rows in tables[arch].items()},
                    'symbols':symbols,'commands':commands,'runs':runs,'work':str(stage)}
            write_json(output/(arch+'.execution.json'),detail)
            report['profiles'][arch]={key:value for key,value in detail.items() if key not in ['symbols','runs']}
            report['profiles'][arch]['run_count']=len(runs)
        require(all(sha(regular(REPO/path).read_bytes())==value for path,value in controls.items()),
                'Source controls changed during compilation')
        report['passed']=True
        print('H700_FOUR_TABLE_LIBRARY_HOST_PASS',flush=True)
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        write_json(output/'result.json',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    constrained()
    build(args.work,args.output)
