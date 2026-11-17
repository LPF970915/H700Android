"""Build/execute bounded ten-profile panel components in ordinary files only.

No device, card, image, kernel source or frozen release inputs are modified.
Use the constrained shared-lock wrapper. Complete events come from the pinned
ten-original-binary execution audit, not model geometry or inferred timings.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO/'tools'), str(REPO/'tools/release')]
from package_h700_v6a import constrained
import h700_panel_profile_uboot as ub
import h700_panel_init_tables as old_tables
from models import MODEL_PROFILE
import panel_codec as codec

TRACE = REPO/'out/rg34xx-boot-analysis-20261114/twelve-uboot-streams-20261116-v1/tables.json'
TRACE_SHA = 'be67cd4f51b6216f22645ab636b38c1f97a02e01a0d1aaca011dd0c538c368d3'
C_SOURCE = HERE/'panel_programs.c'
CLANG = old_tables.CLANG
MODELS = ('rg34xxsp','rg35xxh','rg34xx','rgcubexx','rg35xxplus',
          'rg28xx','rg40xxh','rg40xxv','rg35xxsp','rg35xxpro')
ORIGINALS = {
    'uboot': REPO/'out/roc-os-h700-universal-rg35xxh-20261107/toc/16793600-u-boot.bin',
    'kernel': REPO/'out/roc-os-h700-universal-rg35xxh-20261107/boot-extracted/kernel',
}
ORIGINAL_SHA = {'uboot':ub.UBOOT_SHA,'kernel':'3328c2fab9f19f7ea6a80e34b0a76238cf594bc631f77e05fec32f8adabad042'}
BOUNDS = {
    'uboot': {'.probe':(0x2637a,0x263f4),'.reader':(0x26424,0x26500),'.bridge_old':(0x26b18,0x26b1c),'.payload':(0x26b28,0x27a04)},
    'kernel': {'.bridge_boe':(0x3a2b50,0x3a2b54),'.dispatch':(0x3a2b60,0x3a3460),
               '.bridge_old':(0x3a3460,0x3a3464),'.payload':(0x3a3480,0x3a482c)},
}
ENTRIES = {'uboot':(0x26424,0x26b18,0x26afc),'kernel':(0x3a2b50,0x3a3460,0x3a4840)}
OP = {'COMMAND':1,'DATA':2,'WAIT_MS':3}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def load_streams():
    raw=TRACE.read_bytes()
    require(sha(raw)==TRACE_SHA,'Pinned complete ten-model streams changed')
    trace=json.loads(raw)
    streams={}
    for index,model in enumerate(MODELS):
        require(MODEL_PROFILE[model]==index,'Explicit electrical profile order changed')
        streams[index]={}
        for branch in ('old','boe'):
            record=trace['models'][model]['branches'][branch]
            events=tuple((OP[k],v) for k,v in record['events'])
            require(len(events)==record['event_count'] and sha(bytes(v for e in events for v in e))==record['opcode_value_u8_sha256'],
                    'Full pinned event stream identity')
            streams[index][branch]=events
    return streams


def parse_program(raw,count,pid):
    """Independent full-token validator; retain each decoded range descriptor."""
    blocks=[];pos=cursor=0
    while pos<len(raw):
        token=raw[pos];pos+=1
        if token&128:
            require(pos+2<=len(raw),'Truncated copy token')
            word=((token&127)<<16)|(raw[pos]<<8)|raw[pos+1];pos+=2
            source,offset,size=word>>19,(word>>9)&1023,(word&511)+3
            require(source<=pid and (source<pid or offset+size<=cursor),'Forward/cyclic copy')
            block={'cursor':cursor,'count':size,'source':source,'offset':offset}
        elif token in (1,2,3):
            require(pos<len(raw),'Truncated single token')
            block={'cursor':cursor,'count':1,'literal':[({1:3,2:1,3:2}[token],raw[pos])]};pos+=1
            size=1
        elif 4<=token<=126:
            data=token-3
            require(pos+data+1<=len(raw),'Truncated grouped command')
            values=[(1,raw[pos])]+[(2,x) for x in raw[pos+1:pos+data+1]]
            pos+=data+1;size=len(values)
            block={'cursor':cursor,'count':size,'literal':values}
        else:
            raise ValueError('Invalid literal token')
        cursor+=size
        require(cursor<=count,'Encoded events exceed count')
        blocks.append(block)
    require(cursor==count,'Encoded event count differs')
    return blocks


def review_codec(streams):
    source=[rows for branches in streams.values() for rows in branches.values()]
    originals,encoded=codec.compile_programs(source)
    require(len(originals)==11,'Expected eleven unique complete streams')
    counts=[len(x) for x in originals]
    parsed=[parse_program(raw,count,pid) for pid,(raw,count) in enumerate(zip(encoded,counts))]
    cache={}
    def event(pid,index):
        require(0<=pid<len(parsed) and 0<=index<counts[pid],'Independent lookup range')
        key=pid,index
        if key in cache:return cache[key]
        for block in parsed[pid]:
            if block['cursor']<=index<block['cursor']+block['count']:
                relative=index-block['cursor']
                if 'literal' in block:
                    answer=block['literal'][relative],1
                else:
                    value,depth=event(block['source'],block['offset']+relative)
                    answer=value,depth+1
                cache[key]=answer
                return answer
        raise ValueError('Independent lookup not covered')
    maximum=0
    for pid,expected in enumerate(originals):
        require(codec.decode(encoded,counts,pid)==list(expected),'Codec full roundtrip')
        for index,want in enumerate(expected):
            got,depth=event(pid,index)
            require(got==want,'Independent per-event decode differs')
            maximum=max(maximum,depth)
        for start,count in [(0,0),(0,1),(len(expected)-1,1),(len(expected)//2,7)]:
            count=min(count,len(expected)-start)
            require(codec.decode(encoded,counts,pid,start,count)==list(expected[start:start+count]),'Codec sliced roundtrip')
    require(maximum<=17,'Compiled iterative event_at depth bound exceeded')
    mapping=[[originals.index(streams[p][branch]) for branch in ('old','boe')] for p in range(10)]
    return originals,encoded,mapping,{'programs':len(originals),'counts':counts,
        'compressed_bytes':sum(map(len,encoded)),'maximum_lookup_depth':maximum,
        'all_events_independent_lookup':sum(counts),'full_and_sliced_decode':True,
        'encoded_sha256':[sha(x) for x in encoded],'profile_branch_programs':mapping}


def table_assembly(arch,originals,encoded,mapping,offset_values=None):
    thumb=arch=='uboot'
    lines=['.syntax unified','.thumb'] if thumb else []
    lines+=['.section '+('.reader' if thumb else '.text.panel_lookup')+',"ax",%progbits','.p2align 2','.global panel_blob','.type panel_blob,%function']
    if thumb:
        lines+=['.thumb_func','panel_blob:',f'cmp r0,#{len(encoded)}','bhs 1f','adr.w r1,.Loffsets',
                'ldrh.w r0,[r1,r0,lsl #1]','add r0,r1,r0','bx lr','1:','movs r0,#0','bx lr']
    else:
        lines+=['panel_blob:',f'cmp w0,#{len(encoded)}','b.hs 1f','adr x1,.Loffsets',
                'ldrh w0,[x1,w0,uxtw #1]','add x0,x1,w0,uxtw','ret','1:','mov x0,xzr','ret']
    lines+=['.size panel_blob,.-panel_blob','.p2align 2',
            '.global panel_select','.type panel_select,%function']
    if thumb:
        lines+=['.thumb_func','panel_select:',
                'cmp r1,#1','ite eq','moveq r1,#1','movne r1,#0',
                'add r0,r1,r0,lsl #1','adr.w r1,.Lprofile_map','ldrb r0,[r1,r0]','bx lr']
    else:
        lines+=['panel_select:','cmp w0,#10','csel w0,w0,wzr,lo','cmp w1,#1','cset w1,eq',
                'add w0,w1,w0,lsl #1','adr x1,.Lprofile_map','ldrb w0,[x1,w0,uxtw]','ret']
    lines+=['.size panel_select,.-panel_select','.p2align 2','.global panel_offset_table','panel_offset_table:','.Loffsets:']
    lines+=['.hword '+(str(offset_values[i]) if offset_values is not None else
                      '0' if thumb else '.Lprogram%d-.Loffsets'%i) for i in range(len(encoded))]
    lines+=['.Lprofile_map:','.byte '+','.join(str(x) for pair in mapping for x in pair)]
    if thumb:lines+=['.section .text.panel_programs,"ax",%progbits']
    for i,(events,raw) in enumerate(zip(originals,encoded)):
        lines+=['.p2align 1','.global panel_program_%d'%i,'.Lprogram%d:'%i,'panel_program_%d:'%i,
                '.hword %d,%d'%(len(events),len(raw))]
        lines+=['.byte '+','.join(str(x) for x in raw[n:n+32]) for n in range(0,len(raw),32)]
    lines+=['.section .note.GNU-stack,"",%progbits','']
    return '\n'.join(lines)


def bridge_assembly(arch,probe_offsets=None):
    if arch=='uboot':
        source='\n'.join(line for line in ub.assembly().splitlines() if not line.startswith('.thumb_set '))
        source=source.replace('.section .text.roc_panel_init_bridge,','.section .reader,').replace('.section .text.roc_profile_read_uboot,','.section .reader,')
        source=source.replace('cmp r0,#1\n    bne .Lprofile_zero\n    movs r0,#1','cmp r0,#9\n    bhi .Lprofile_zero')
        source=source.replace('    movs r3,#0\n    str r3,[sp]\n','')
        source+='\n.section .bridge_old,"ax",%progbits\n.thumb\n.p2align 1\n.global roc_old_redirect\n.thumb_func\nroc_old_redirect:\n b.w roc_panel_init_bridge\n'
        source+='''
.section .probe,"ax",%progbits
.thumb
.global roc_probe_entry
.type roc_probe_entry,%function
.thumb_func
roc_probe_entry:
    bl roc_profile_read_uboot
    movs r5,#0
    cmp r0,#3
    beq .Lprobe_done
    cmp r0,#5
    beq .Lprobe_done
.global roc_probe_load_config
roc_probe_load_config:
    ldr.n r2,[pc,#PROBE_CFG]
    ldr r3,[r2]
    dmb sy
    bic r3,r3,#0xf000000
    orr r3,r3,#0x6000000
    dmb sy
    str r3,[r2]
    ldr r3,[r2]
    dmb sy
    subs r0,#6
    cmp r0,#2
    bls .Lprobe_read
.global roc_probe_load_pull
roc_probe_load_pull:
    ldr.n r2,[pc,#PROBE_PULL]
    ldr r3,[r2]
    dmb sy
    bic r3,r3,#0x3000
    orr r3,r3,#0x1000
    dmb sy
    str r3,[r2]
    ldr r3,[r2]
    dmb sy
.Lprobe_read:
.global roc_probe_load_data
roc_probe_load_data:
    ldr.n r2,[pc,#PROBE_DATA]
    ldr r5,[r2]
    dmb sy
    eor r5,r5,#64
    ubfx r5,r5,#6,#1
.Lprobe_done:
.global roc_probe_load_state
roc_probe_load_state:
    ldr.n r4,[pc,#PROBE_STATE]
    str r5,[r4]
    cmp r5,#1
    bne.w roc_old_redirect
    b.w roc_panel_init_bridge
.size roc_probe_entry,.-roc_probe_entry
'''
        for key in ('CFG','PULL','DATA','STATE'):
            source=source.replace('PROBE_'+key,str(0 if probe_offsets is None else probe_offsets[key]))
        return source
    source=(REPO/'tools/release/h700_panel_profile_kernel.S').read_text()
    source='\n'.join(line for line in source.splitlines() if not line.startswith('.set '))+'\n'
    source=source.replace('.section .profile_dispatch,','.section .dispatch,')
    source=source.replace('cmp w0, #1\n    cset w0, eq','cmp w0, #10\n    csel w0, w0, wzr, lo')
    return source


def linker(arch):
    base=old_tables.ARCH[arch]['base']
    if arch=='uboot':
        declarations='''roc_fdt_path_offset = 0x4a067fdd;
roc_fdt_getprop = 0x4a067e7d;
roc_table_apply = panel_apply;
roc_panel_init_tail = 0x4a026afd;
panel_cmd = 0x4a027e3d;
panel_data = 0x4a027fcd;
panel_wait = 0x4a02621d;
'''
        entry='roc_panel_init_bridge'
    else:
        declarations='''kernel_profile_get_item = 0xffffff8008400298;
kernel_panel_apply_frozen = panel_apply;
kernel_original_epilogue = 0xffffff8008424840;
panel_cmd = 0xffffff8008421f18;
panel_data = 0xffffff800842247c;
panel_wait = 0xffffff800841a2d8;
'''
        entry='kernel_bridge_boe'
    lines=['ENTRY('+entry+')','SECTIONS {']
    for name,(start,end) in BOUNDS[arch].items():
        inputs=('*(.text.panel_apply) *(.text*) *(.rodata*)' if name=='.payload' else
                'bridge.o(.reader) table.o(.reader)' if name=='.reader' else '*('+name+')')
        lines+=[' %s 0x%x : { %s }'%(name,base+start,inputs)]
    lines+=[' /DISCARD/ : { *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }']
    for name,(start,end) in BOUNDS[arch].items():
        lines+=[' ASSERT(ADDR(%s) + SIZEOF(%s) <= 0x%x, "%s limit")'%(name,name,base+end,name)]
    lines+=['}',declarations]
    return '\n'.join(lines)


def elf_sections(path,arch):
    raw=path.read_bytes();thumb=arch=='uboot';p=old_tables.ARCH[arch]
    require(raw[:7]==b'\x7fELF'+bytes([1 if thumb else 2,1,1]),'ELF encoding')
    require(struct.unpack_from('<HH',raw,16)==(2,p['machine']),'ELF machine/type')
    if thumb:
        shoff=struct.unpack_from('<I',raw,32)[0];stride,count,nsindex=struct.unpack_from('<HHH',raw,46);fmt='<10I'
    else:
        shoff=struct.unpack_from('<Q',raw,40)[0];stride,count,nsindex=struct.unpack_from('<HHH',raw,58);fmt='<II4QII2Q'
    require(stride==struct.calcsize(fmt),'ELF section stride')
    hs=[struct.unpack_from(fmt,raw,shoff+stride*i) for i in range(count)]
    ns=raw[hs[nsindex][4]:hs[nsindex][4]+hs[nsindex][5]]
    sections=[];symbols={}
    for h in hs:
        name=ns[h[0]:ns.index(0,h[0])].decode()
        require(not(h[1] in (4,9) and h[5]),'Unresolved ELF relocations')
        if h[2]&2 and h[5]:
            require(name in BOUNDS[arch] and h[1]==1,'Unexpected allocated section '+name)
            start,limit=BOUNDS[arch][name]
            require(h[3]-p['base']==start and 0<h[5]<=limit-start,'Allocated section bounds')
            sections.append({'name':name,'offset':start,'data':raw[h[4]:h[4]+h[5]]})
        if h[1]==2:
            st=hs[h[6]];strings=raw[st[4]:st[4]+st[5]]
            for pos in range(h[4],h[4]+h[5],h[9]):
                if thumb:n,value,size,info,other,index=struct.unpack_from('<IIIBBH',raw,pos)
                else:n,info,other,index,value,size=struct.unpack_from('<IBBHQQ',raw,pos)
                label=strings[n:strings.index(0,n)].decode()
                if label:symbols[label]=value
    require({s['name'] for s in sections}==set(BOUNDS[arch]),'Missing sections')
    return sorted(sections,key=lambda x:x['offset']),symbols


def expected(streams,arch,profile,branch,getter_ok=True):
    profile=profile if getter_ok and 0<=profile<10 else 0
    rows=list(streams[profile]['boe' if branch==1 else 'old'])
    if arch=='kernel' and profile==0 and branch!=1:rows.append((3,100))
    return rows


def execute(arch,patched,sections,symbols,streams,profile,branch,slide=0,*,getter_ok=True,wrong_event=False,direct=False,full=False,once=0):
    import unicorn as uc
    from unicorn import arm_const as ar,arm64_const as aa
    thumb=arch=='uboot';p=old_tables.ARCH[arch]
    base=(p['base'] if thumb else 0x08080000)+slide
    cpu=uc.Uc(uc.UC_ARCH_ARM if thumb else uc.UC_ARCH_ARM64,uc.UC_MODE_THUMB if thumb else uc.UC_MODE_ARM)
    mapped=(len(patched)+4095)&~4095
    cpu.mem_map(base,mapped,uc.UC_PROT_ALL if full else uc.UC_PROT_READ|uc.UC_PROT_EXEC)
    cpu.mem_write(base,patched)
    trace=json.loads(TRACE.read_text())
    if full:
        require(thumb and not direct,'Full original outer init is U-Boot only')
        relocated,_=ub._relocate_original_for_emulator(ORIGINALS[arch].read_bytes(),218,slide)
        cpu.mem_write(base,relocated)
        for section in sections:cpu.mem_write(base+section['offset'],section['data'])
        once_cell=base+0xf3db0;type_cell=base+0xf3dac
        cpu.mem_write(once_cell,struct.pack('<I',once))
        cpu.mem_map(0x03000000,0x100000)
        cpu.mem_write(0x0300b0a0,struct.pack('<I',0 if branch==1 else 64))
    stack,sp0=0x70000000,0x7000ff00
    cpu.mem_map(stack,0x10000);cpu.mem_map(0x60000000,0x1000)
    ptr=0x60000000;cpu.mem_write(ptr,struct.pack('>I',profile&0xffffffff))
    if thumb:cpu.mem_write(base+ub.WORKING_FDT_CELL,struct.pack('<I',ptr))
    regs={i:getattr(ar,'UC_ARM_REG_R'+str(i)) for i in range(13)} if thumb else {i:getattr(aa,'UC_ARM64_REG_X'+str(i)) for i in range(31)}
    spreg=ar.UC_ARM_REG_SP if thumb else aa.UC_ARM64_REG_SP
    lrreg=ar.UC_ARM_REG_LR if thumb else aa.UC_ARM64_REG_LR
    pcreg=ar.UC_ARM_REG_PC if thumb else aa.UC_ARM64_REG_PC
    preserved=list(range(4,12)) if thumb else list(range(18,30))
    for i in preserved:cpu.reg_write(regs[i],0x12340000+i*0x100)
    cpu.reg_write(regs[5 if thumb else 19],branch)
    initial={i:cpu.reg_read(regs[i]) for i in preserved}
    cpu.reg_write(spreg,sp0);sentinel=base+0x1000
    cpu.reg_write(lrreg,sentinel+int(thumb))
    boe,old,tail=ENTRIES[arch]
    helpers={p['command']:1,p['data']:2,p['delay']:3}
    ranges=[(s['offset'],s['offset']+len(s['data'])) for s in sections]
    effective=profile if getter_ok and 0<=profile<10 else 0
    effective_branch=0 if full and effective in (3,5) else branch
    wanted=expected(streams,arch,profile,effective_branch,getter_ok)
    if full:wanted=[(3,x) for x in (15,50,100)]+wanted
    calls=[];api=[];stops=[];blocks=0;minimum_sp=sp0;reads=[];writes=[]
    def string(address):
        return bytes(cpu.mem_read(address,80)).split(b'\0',1)[0].decode('ascii')
    def clobber(value=None):
        lr=cpu.reg_read(lrreg)
        for i in ([0,1,2,3,12] if thumb else list(range(18))):cpu.reg_write(regs[i],0x55aa0000+i)
        if value is not None:cpu.reg_write(regs[0],value&0xffffffff)
        cpu.reg_write(ar.UC_ARM_REG_APSR_NZCV if thumb else aa.UC_ARM64_REG_NZCV,0xa0000000)
        cpu.reg_write(pcreg,lr)
    def hook(machine,address,size,unused):
        nonlocal minimum_sp
        off=address-base
        if off==(0x1000 if direct or full else tail):stops.append(True);cpu.emu_stop();return
        require(cpu.reg_read(spreg)%(8 if thumb else 16)==0,'Helper/API stack alignment')
        minimum_sp=min(minimum_sp,cpu.reg_read(spreg))
        if off in helpers:
            kind=helpers[off];raw=cpu.reg_read(regs[0]);value=raw&255
            argument=value if thumb or kind==3 or value<128 else 0x100000000+value-256
            require(raw==argument,'Unsigned/signed helper ABI')
            if wrong_event and not calls:kind=2 if kind==1 else 1
            calls.append((kind,value))
            require(len(calls)<=len(wanted) and calls[-1]==wanted[len(calls)-1],'Complete event stream mismatch')
            require(cpu.reg_read(regs[9 if thumb else 18])==initial[9 if thumb else 18],'Reserved r9/x18 changed')
            clobber();return
        if thumb and off==ub.FDT_PATH_OFFSET:
            require(cpu.reg_read(regs[0])==ptr and string(cpu.reg_read(regs[1]))==ub.PATH,'FDT path ABI')
            api.append('path');clobber(72 if getter_ok else -1);return
        if thumb and off==ub.FDT_GETPROP:
            require(cpu.reg_read(regs[0])==ptr and cpu.reg_read(regs[1])==72 and string(cpu.reg_read(regs[2]))==ub.PROPERTY,'FDT property ABI')
            cpu.mem_write(cpu.reg_read(regs[3]),struct.pack('<I',4));api.append('getprop');clobber(ptr);return
        if not thumb and off==0x380298:
            require(string(cpu.reg_read(regs[0]))=='lcd0' and string(cpu.reg_read(regs[1]))==ub.PROPERTY and cpu.reg_read(regs[3])==1,'Kernel getter ABI')
            cpu.mem_write(cpu.reg_read(regs[2]),struct.pack('<I',profile&0xffffffff))
            api.append('get_item');clobber(1 if getter_ok else 0);return
        if full and off==0xe620:
            require(string(cpu.reg_read(regs[0]))=='lcd_type' and string(cpu.reg_read(regs[1]))==('boe' if effective_branch==1 else 'old'),'Original LCD environment producer')
            api.append('env_lcd_type');clobber(0);return
        if full and off==0x6a7bc:api.append('printf');clobber(0);return
        raise ValueError('Undeclared hooked target '+hex(off))
    hooks=set(helpers)|({ub.FDT_PATH_OFFSET,ub.FDT_GETPROP} if thumb else {0x380298})|{0x1000 if direct or full else tail}
    if full:hooks|={0xe620,0x6a7bc}
    for off in hooks:cpu.hook_add(uc.UC_HOOK_CODE,hook,begin=base+off,end=base+off)
    def block(machine,address,size,unused):
        nonlocal blocks
        blocks+=1;off=address-base
        require(off in hooks or any(a<=off<b and off+size<=b for a,b in ranges) or
                (full and ((0x262e4<=off and off+size<=0x26424) or (0x26afc<=off and off+size<=0x26b18) or
                           (0x279fe<=off and off+size<=0x27a04))),
                'Executed outside bounded code/helper '+hex(off))
    cpu.hook_add(uc.UC_HOOK_BLOCK,block)
    def write(machine,access,address,size,value,unused):
        if full and 0x03000000<=address<0x03100000:
            writes.append({'address':hex(address),'size':size,'value':value});return
        require(stack<=address and address+size<=stack+0x10000 or
                full and address in (once_cell,type_cell) and size==4,'Machine code wrote outside declared stack/state/MMIO')
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE,write)
    if full:
        def read(machine,access,address,size,value,unused):
            if 0x03000000<=address<0x03100000:reads.append({'address':hex(address),'size':size,'value':int.from_bytes(cpu.mem_read(address,size),'little')})
        cpu.hook_add(uc.UC_HOOK_MEM_READ,read)
    if direct:
        cpu.reg_write(regs[0],profile&0xffffffff);cpu.reg_write(regs[1],branch)
        entry=(symbols['panel_apply']&~1)-p['base']
    else:entry=0x262e4 if full else boe if branch==1 else old
    cpu.emu_start(base+entry+int(thumb),base+mapped,timeout=20_000_000,count=20_000_000)
    require(stops==[True] and calls==wanted,'Missing normal tail/return or incomplete events')
    require(cpu.reg_read(spreg)==sp0,'Stack not restored')
    require(all(cpu.reg_read(regs[i])==v for i,v in initial.items()),'Callee/reserved register not restored')
    if full:
        reference=next(x for x in trace['reset_probe'][MODELS[effective]] if x['operation']=='init' and
                       x['strap_branch']==('boe' if branch==1 else 'old') and x['controlled_once_initial']==once)
        require(reads==reference['mmio_reads'] and writes==reference['mmio_writes'],'Original model-specific reset/probe MMIO differs')
        require(cpu.mem_read(type_cell,4)==struct.pack('<I',effective_branch),'Original lcd_type state not updated')
        require(api.count('env_lcd_type')==1,'Original LCD environment producer not retained')
    return {'profile_input':profile,'branch':branch,'slide':slide,'direct':direct,'getter_ok':getter_ok,
            'events':len(calls),'event_sha256':sha(bytes(v for e in calls for v in e)),
            'exact_reference':True,'normal_tail_or_return':True,'callee_reserved_SP':True,
            'helper_ABI':True,'blocks':blocks,'maximum_observed_helper_stack_bytes':sp0-minimum_sp,'API_calls':api,
            'full_original_outer_init':full,'controlled_once_initial':once if full else None,
            'reset_probe_MMIO_matches_original_model':True if full else None,
            'mmio_reads':reads if full else None,'mmio_writes':writes if full else None}


def reject(label,fn):
    try:fn()
    except (ValueError,RuntimeError):return {'case':label,'rejected':True}
    raise ValueError('Negative control accepted '+label)


def execute_kernel_parser_outer(patched,sections,symbols,streams,profile,argument,slide=0,once=0):
    """Execute original __setup, original strncmp, reset and final dispatcher.

    The kernel has no PE6 probe in this route. Its original setup callback
    consumes the U-Boot lcd_type= argument, and its original init resets PI14.
    ioremap/getter/printf and serial/delay callbacks are intercepted explicitly.
    """
    import unicorn as uc
    from unicorn import arm64_const as aa
    cpu=uc.Uc(uc.UC_ARCH_ARM64,uc.UC_MODE_ARM)
    base=0x08080000+slide;mapped=(len(patched)+4095)&~4095
    cpu.mem_map(base,mapped,uc.UC_PROT_READ|uc.UC_PROT_EXEC);cpu.mem_write(base,patched)
    state=base+0x113c000+0xce0;state_page=state&~4095
    stack,sp0,scratch,io=0x70000000,0x7000ff00,0x60000000,0x50000000
    for address,size in [(state_page,4096),(base+0x10e2000,4096),(stack,65536),(scratch,4096),(io,4096)]:cpu.mem_map(address,size)
    cpu.mem_write(state,struct.pack('<I',0))
    cpu.mem_write(state+8,struct.pack('<Q',io if once else 0))
    cpu.mem_write(scratch,(b'' if argument is None else argument.encode())+bytes(80))
    cpu.mem_write(scratch+128,struct.pack('<I',profile&0xffffffff))
    regs={i:getattr(aa,'UC_ARM64_REG_X'+str(i)) for i in range(31)}
    initial={i:0x12340000+i*0x100 for i in range(18,30)}
    for i,v in initial.items():cpu.reg_write(regs[i],v)
    cpu.reg_write(aa.UC_ARM64_REG_SP,sp0);cpu.reg_write(aa.UC_ARM64_REG_LR,base+0x1000)
    cpu.reg_write(regs[0],0 if argument is None else scratch)
    phase='parser';returns=[];calls=[];api=[];mmio=[];blocks=0
    wanted_branch=1 if argument is not None and argument.startswith('boe') else 0
    effective=profile if profile<10 else 0
    wanted=[(3,x) for x in (15,50,100)]+expected(streams,'kernel',profile,wanted_branch)
    def string(ptr):return bytes(cpu.mem_read(ptr,80)).split(b'\0',1)[0].decode('ascii')
    def clobber(value=0):
        lr=cpu.reg_read(aa.UC_ARM64_REG_LR)
        for i in range(18):cpu.reg_write(regs[i],0x55aa0000+i)
        cpu.reg_write(regs[0],value&0xffffffffffffffff);cpu.reg_write(aa.UC_ARM64_REG_NZCV,0xa0000000)
        cpu.reg_write(aa.UC_ARM64_REG_PC,lr)
    helpers={0x3a1f18:1,0x3a247c:2,0x39a2d8:3}
    def hook(machine,address,size,unused):
        off=address-base
        if off==0x1000:returns.append(phase);cpu.emu_stop();return
        require(cpu.reg_read(aa.UC_ARM64_REG_SP)%16==0,'Kernel outer helper SP alignment')
        require(cpu.reg_read(regs[18])==initial[18],'Kernel outer reserved x18')
        if off in helpers:
            kind=helpers[off];raw=cpu.reg_read(regs[0]);value=raw&255
            wantarg=value if kind==3 or value<128 else 0x100000000+value-256
            require(raw==wantarg,'Kernel outer helper signed-byte ABI')
            calls.append((kind,value));require(calls==wanted[:len(calls)],'Kernel original reset/full stream mismatch')
            clobber();return
        if off==0xda2b0:api.append('printf');clobber();return
        if off==0x380298:
            require(string(cpu.reg_read(regs[0]))=='lcd0' and string(cpu.reg_read(regs[1]))==ub.PROPERTY and cpu.reg_read(regs[3])==1,'Kernel outer profile getter ABI')
            cpu.mem_write(cpu.reg_read(regs[2]),struct.pack('<I',profile&0xffffffff));api.append('get_item');clobber(1);return
        if off==0x1ac34:
            require(cpu.reg_read(regs[0])==0x0300b130 and cpu.reg_read(regs[1])==4,'Original reset ioremap physical/size')
            api.append('ioremap_reset_data');clobber(io);return
        raise ValueError('Unexpected original outer API '+hex(off))
    hooks=set(helpers)|{0x1000,0xda2b0,0x380298,0x1ac34}
    for off in hooks:cpu.hook_add(uc.UC_HOOK_CODE,hook,begin=base+off,end=base+off)
    ranges=[(s['offset'],s['offset']+len(s['data'])) for s in sections]
    ranges += [(0xcdfdb4,0xcdfe30),(0x3278a0,0x327aa8),(0x3a29b0,0x3a2b50),(0x3a4840,0x3a48b8)]
    def block(machine,address,size,unused):
        nonlocal blocks
        blocks+=1;off=address-base
        require(off in hooks or any(a<=off and off+size<=b for a,b in ranges),'Kernel outer escaped code bounds '+hex(off))
    cpu.hook_add(uc.UC_HOOK_BLOCK,block)
    def write(machine,access,address,size,value,unused):
        if address==io and size==4:mmio.append(value);return
        require(stack<=address and address+size<=stack+65536 or state<=address and address+size<=state+16,
                'Kernel parser/outer unexpected write')
    cpu.hook_add(uc.UC_HOOK_MEM_WRITE,write)
    cpu.emu_start(base+0xcdfdb4,base+mapped,timeout=5_000_000,count=100000)
    require(returns==['parser'] and cpu.mem_read(state,4)==struct.pack('<I',wanted_branch),'Original setup parser state/return')
    require(cpu.reg_read(regs[0])==(0 if argument in (None,'') else 1),'Original setup parser return ABI')
    require(cpu.reg_read(aa.UC_ARM64_REG_SP)==sp0 and all(cpu.reg_read(regs[i])==v for i,v in initial.items()),'Kernel parser callee/reserved/SP')
    phase='init';cpu.reg_write(aa.UC_ARM64_REG_LR,base+0x1000)
    cpu.emu_start(base+0x3a29b0,base+mapped,timeout=20_000_000,count=20000000)
    require(returns==['parser','init'] and calls==wanted,'Kernel full init caller return/stream')
    require(mmio==[16384,0,16384],'Original kernel PI14 high/low/high reset sequence')
    require(cpu.reg_read(aa.UC_ARM64_REG_SP)==sp0 and all(cpu.reg_read(regs[i])==v for i,v in initial.items()),'Kernel outer callee/reserved/SP')
    require(api.count('get_item')==1 and api.count('ioremap_reset_data')==int(not once),'Original kernel reset mapping/getter count')
    return {'profile':profile,'argument':argument,'slide':slide,'initial_reset_mapping':once,
            'actual_original_setup_and_strncmp':True,'actual_original_outer_reset':True,
            'no_PE6_hardware_probe_added':True,'lcd_type_branch':wanted_branch,'events':len(calls),
            'PI14_sequence':mmio,'API_calls':api,'caller_return_ABI_reserved_SP':True,'blocks':blocks}


def build(work,output):
    constrained()
    require(not work.exists() and not output.exists(),'Fresh work/output required; preserve failed attempts')
    work.mkdir(parents=True);output.mkdir(parents=True)
    inputs=[Path(__file__),C_SOURCE,HERE/'panel_codec.py',Path(ub.__file__),
            REPO/'tools/release/h700_panel_profile_kernel.S',TRACE,
            REPO/'out/rg34xx-boot-analysis-20261114/panel-electrical-twelve-v1/result.json',
            REPO/'out/rg34xx-boot-analysis-20261114/panel-gamma-color-twelve-v1/result.json']
    controls={str(p.relative_to(REPO)):sha(p.read_bytes()) for p in inputs}
    report={'schema':'roc.ten-profile-compressed-panel-components.v1','passed':False,'scope':__doc__,
            'controls':controls,'trace_sha256':TRACE_SHA,'architectures':{},'negative_controls':[],
            'model_profile_snapshot':dict(MODEL_PROFILE),
            'model_profile_snapshot_sha256':sha(json.dumps(MODEL_PROFILE,sort_keys=True).encode()),
            'non_timing_electrical_review':{
                'exact_original_five_DTS_nodes':'out/rg34xx-boot-analysis-20261114/panel-electrical-twelve-v1/result.json',
                'gamma_color_twenty_actual_original_callback_outputs':'out/rg34xx-boot-analysis-20261114/panel-gamma-color-twelve-v1/result.json',
                'PE6_variant_adapter':'Only the original 0x2637a..0x263f4 probe/printf window is changed; original reset/power/literal pool/environment tail retained.',
                'kernel_setup_consumer':'Original kernel consumes lcd_type=; no PE6 write is added to the kernel.',
                'physical_acceptance':False}}
    write_json(output/'result.json',report)
    try:
        streams=load_streams()
        print('PHASE=codec_compile_review',flush=True)
        originals,encoded,mapping,review=review_codec(streams)
        report['codec']=review;write_json(output/'codec.json',review)
        import unicorn
        require(unicorn.__version__=='2.1.4','Isolated Unicorn2.1.4 required')
        for arch,p in old_tables.ARCH.items():
            print('PHASE=compile_'+arch,flush=True)
            stage=work/arch;stage.mkdir()
            (stage/'table.S').write_text(table_assembly(arch,originals,encoded,mapping))
            (stage/'bridge.S').write_text(bridge_assembly(arch))
            (stage/'panel.ld').write_text(linker(arch));shutil.copyfile(C_SOURCE,stage/'panel.c')
            flags=['--target='+p['target'],'-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector',
                '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-jump-tables',
                '-ffunction-sections','-fdata-sections','-fno-pic','-fno-pie','-Wall','-Wextra','-Werror']
            archflags=['-mthumb','-march=armv7-a','-mfloat-abi=soft','-ffixed-r9'] if arch=='uboot' else ['-march=armv8-a','-mgeneral-regs-only','-ffixed-x18','-DPANEL_SIGNED_BYTE','-DPANEL_KERNEL_LEGACY_WAIT']
            commands=[[str(CLANG/'clang.real')]+flags+archflags+['-c','panel.c','-o','panel.o']]
            commands += [[str(CLANG/'clang.real'),'--target='+p['target']]+archflags+['-c',s+'.S','-o',s+'.o'] for s in ('table','bridge')]
            commands += [[str(CLANG/'ld.lld'),'-T','panel.ld','--no-undefined','--fatal-warnings','--build-id=none','-Map=panel.map','-o','panel.elf','panel.o','table.o','bridge.o']]
            for command in commands:subprocess.run(command,cwd=stage,check=True)
            sections,symbols=elf_sections(stage/'panel.elf',arch)
            if arch=='uboot':
                # Thumb has no cross-section 16-bit PC-relative relocation.
                # Resolve the compact relative offsets in a checked second link;
                # section sizes and all symbol addresses must remain identical.
                first_symbols=dict(symbols)
                offsets=[symbols['panel_program_'+str(i)]-symbols['panel_offset_table'] for i in range(len(encoded))]
                require(all(0<=x<=65535 for x in offsets),'Relative program offset range')
                probe_offsets={}
                for key,label,target in [('CFG','config',0x26404),('PULL','pull',0x26408),('DATA','data',0x26410),('STATE','state',0x26414)]:
                    pc=(symbols['roc_probe_load_'+label]+4)&~3
                    probe_offsets[key]=p['base']+target-pc
                require(all(0<=x<=1020 and x%4==0 for x in probe_offsets.values()),'Original probe literal PC-relative range')
                for filename in ('table.S','bridge.S','panel.elf','panel.map'):
                    shutil.copyfile(stage/filename,stage/(filename+'.first'))
                (stage/'table.S').write_text(table_assembly(arch,originals,encoded,mapping,offsets))
                (stage/'bridge.S').write_text(bridge_assembly(arch,probe_offsets))
                for command in (commands[1],commands[2],commands[-1]):subprocess.run(command,cwd=stage,check=True)
                sections,symbols=elf_sections(stage/'panel.elf',arch)
                require(symbols==first_symbols,'Second-link symbol/layout drift')
            original=ORIGINALS[arch].read_bytes()
            require(sha(original)==ORIGINAL_SHA[arch],'Frozen original identity')
            if arch=='uboot':ub.guard_original(original)
            patched=bytearray(original)
            for section in sections:
                first=section['offset'];last=first+len(section['data'])
                if arch=='uboot':
                    for address,kind in struct.iter_unpack('<II',original[ub.RELDYN_START:ub.RELDYN_END]):
                        require(kind==23 and not(first<address-ub.BASE+4 and address-ub.BASE<last),'Original relocation target overwritten')
                patched[first:last]=section['data']
            cursor=0
            for section in sections:
                require(patched[cursor:section['offset']]==original[cursor:section['offset']],'Unbounded driver delta')
                cursor=section['offset']+len(section['data'])
            require(patched[cursor:]==original[cursor:],'Unbounded driver suffix delta')
            # Check each compressed stream/header in the final linked component.
            for pid,(events,raw) in enumerate(zip(originals,encoded)):
                offset=symbols['panel_program_'+str(pid)]-p['base']
                require(patched[offset:offset+4+len(raw)]==struct.pack('<HH',len(events),len(raw))+raw,'Final linked compressed program mismatch')
                table=symbols['panel_offset_table']-p['base']
                require(struct.unpack_from('<H',patched,table+pid*2)[0]==offset-table,'Final relative program pointer mismatch')
            listing=subprocess.check_output([p['objdump'],'-d',str(stage/'panel.elf')],text=True)
            (output/(arch+'.disasm.txt')).write_text(listing)
            shutil.copyfile(stage/'panel.elf',output/(arch+'.panel.elf'))
            manifest=[]
            for i,section in enumerate(sections):
                part=output/(arch+'.'+str(i)+'.bin');part.write_bytes(section['data'])
                manifest.append({'name':section['name'],'offset':section['offset'],'bytes':len(section['data']),
                    'sha256':sha(section['data']),'file':str(part),'before_sha256':sha(original[section['offset']:section['offset']+len(section['data'])])})
            patched_path=output/(arch+'.patched.bin');patched_path.write_bytes(patched)
            report['architectures'][arch]={'original_sha256':sha(original),'original_bytes':len(original),'patched_sha256':sha(patched),
                'file':str(patched_path),'patched_file':str(patched_path),'sections':manifest,'commands':commands,'ELF_no_relocations':True}
            if arch=='uboot':
                report['architectures'][arch]['original_relocation_records_unchanged']=(ub.RELDYN_END-ub.RELDYN_START)//8
                report['architectures'][arch]['all_original_relocation_targets_outside_patch_spans']=True
                report['architectures'][arch]['two_link_symbol_layout_identical']=True
            write_json(output/'result.json',report)
            print('PHASE=execute_'+arch,flush=True)
            runs=[]
            for profile in range(10):
                for branch in (0,1):
                    for slide in (0,0x01000000):
                        runs.append(execute(arch,bytes(patched),sections,symbols,streams,profile,branch,slide))
                print('PROFILE_PASS='+arch+':'+str(profile),flush=True)
            for profile in (10,99,0xffffffff):
                for branch in (0,1):
                    runs.append(execute(arch,bytes(patched),sections,symbols,streams,profile,branch))
                    runs.append(execute(arch,bytes(patched),sections,symbols,streams,profile,branch,direct=True))
            for branch in (0,1,2):
                runs.append(execute(arch,bytes(patched),sections,symbols,streams,9,branch,getter_ok=False))
                runs.append(execute(arch,bytes(patched),sections,symbols,streams,0,branch,direct=True))
            report['negative_controls'].append(reject(arch+'_wrong_helper_event',lambda:execute(arch,bytes(patched),sections,symbols,streams,0,0,wrong_event=True)))
            corrupted=bytearray(patched)
            first=symbols['panel_program_'+str(mapping[0][0])]-p['base']
            struct.pack_into('<H',corrupted,first,641)
            report['negative_controls'].append(reject(arch+'_event_count_over_640',lambda:execute(arch,bytes(corrupted),sections,symbols,streams,0,0)))
            corrupted=bytearray(patched);struct.pack_into('<H',corrupted,first+2,0)
            report['negative_controls'].append(reject(arch+'_truncated_program',lambda:execute(arch,bytes(corrupted),sections,symbols,streams,0,0)))
            write_json(output/(arch+'.execution.json'),{'passed':True,'runs':runs})
            report['architectures'][arch]['dispatch_runs']=len(runs)
            report['architectures'][arch]['execution_sha256']=sha((output/(arch+'.execution.json')).read_bytes())
            if arch=='uboot':
                print('PHASE=execute_original_reset_probe_uboot',flush=True)
                full=[]
                for profile in range(10):
                    for branch in (0,1):
                        for once in (0,1):
                            for slide in (0,0x01000000):
                                full.append(execute(arch,bytes(patched),sections,symbols,streams,profile,branch,slide,full=True,once=once))
                    print('PROBE_PROFILE_PASS='+str(profile),flush=True)
                for profile in (10,99,0xffffffff):
                    for branch in (0,1):full.append(execute(arch,bytes(patched),sections,symbols,streams,profile,branch,full=True))
                write_json(output/'uboot.original-reset-probe.json',{'passed':True,'runs':full})
                report['architectures'][arch]['original_outer_reset_probe_full_stream_cases']=len(full)
                from h700_panel_profiles import fdt_properties,KEY
                fdt=bytearray((REPO/'out/rg34xx-boot-analysis-20261114/panel-profile-carrier-v3/early.rg35h.dtb').read_bytes())
                _,properties=fdt_properties(fdt);cell=properties[KEY]['offset']
                reader_section=next(s for s in sections if s['name']=='.reader')
                reader=(symbols['roc_profile_read_uboot']&~1)-p['base']
                real=[]
                for profile in list(range(10))+[10,99,0xffffffff]:
                    chosen=bytearray(fdt);struct.pack_into('>I',chosen,cell,profile)
                    for slide in (0,0x01000000):
                        real.append(ub.execute_actual_reader(original,reader_section['data'],reader,chosen,profile if profile<10 else 0,slide=slide))
                short=bytearray(fdt);struct.pack_into('>I',short,cell-8,3)
                missing=(REPO/'out/rg34xx-boot-analysis-20261114/early-fdt-at-17954816.dtb').read_bytes()
                for label,value in [('short',short),('missing',missing)]:
                    for slide in (0,0x01000000):real.append(dict(ub.execute_actual_reader(original,reader_section['data'],reader,value,0,slide=slide),case=label))
                for slide in (0,0x01000000):real.append(ub.execute_actual_reader(original,reader_section['data'],reader,b'\0'*4096,0,slide=slide,null_fdt=True))
                write_json(output/'uboot.real-libfdt-reader.json',{'passed':True,'runs':real})
                report['architectures'][arch]['actual_original_libfdt_cases']=len(real)
            else:
                print('PHASE=execute_original_kernel_setup_reset',flush=True)
                outer=[]
                for profile in range(10):
                    for argument in ('old','boe'):
                        for once in (0,1):
                            for slide in (0,0x01000000):
                                outer.append(execute_kernel_parser_outer(bytes(patched),sections,symbols,streams,profile,argument,slide,once))
                    print('KERNEL_OUTER_PROFILE_PASS='+str(profile),flush=True)
                for argument in (None,'','b','bo','boex','BOE','unknown'):
                    outer.append(execute_kernel_parser_outer(bytes(patched),sections,symbols,streams,0,argument))
                write_json(output/'kernel.original-setup-reset.json',{'passed':True,'runs':outer})
                report['architectures'][arch]['original_setup_reset_full_stream_cases']=len(outer)
                report['architectures'][arch]['original_setup_evidence']={
                    'kernel_original_sha256':sha(original),'setup_string_offset':0xd02d54,
                    'setup_string':original[0xd02d54:0xd02d54+10].decode().rstrip('\0'),
                    'setup_callback_offset':0xcdfdb4,'setup_callback_sha256':sha(original[0xcdfdb4:0xcdfe30]),
                    'RELA_string_record_offset':0xe566a8,'RELA_string_record':original[0xe566a8:0xe566c0].hex(),
                    'RELA_callback_record_offset':0xe566c0,'RELA_callback_record':original[0xe566c0:0xe566d8].hex(),
                    'lcd_type_global_VA':hex(0xffffff80091bcce0),
                    'kernel_PE6_probe':False,'reason':'Original setup consumes lcd_type=; original panel init only resets PI14 and reads that state.'}
            write_json(output/'result.json',report)
        require(all(sha((REPO/path).read_bytes())==value for path,value in controls.items()),'Build controls changed')
        report['passed']=True
        print('TEN_PROFILE_COMPRESSED_PANEL_COMPONENTS_PASS',flush=True)
    except BaseException as error:
        report['error']=type(error).__name__+': '+str(error)
        raise
    finally:write_json(output/'result.json',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build(args.work,args.output)
