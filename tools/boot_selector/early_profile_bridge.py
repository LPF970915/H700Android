"""Build and execute the pinned early-profile hook in ordinary U-Boot only.

No card/device I/O or image writer. The output is an engineering component,
requiring the parent's guarded TOC/FDT/boot integration and physical testing.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'tools'), str(REPO / 'tools/release')]
from package_h700_v6a import constrained
import h700_panel_profile_uboot as ub

BASE = ub.BASE
START, LIMIT = 0x26500, 0x26afc
ORIGINAL = REPO / 'out/roc-os-h700-universal-rg35xxh-20261107/toc/16793600-u-boot.bin'
DISPATCH = REPO / 'out/rg34xx-boot-analysis-20261114/panel-dispatch-v5/uboot.patched.bin'
DISPATCH_SHA = '9ef33bddf7b614354fb4272e6c2564da27e8d43d473a15d223740444ae6b9956'
FDT = REPO / 'out/rg34xx-boot-analysis-20261114/panel-profile-carrier-v3/early.default.dtb'
CLANG = Path('/home/lpf/h700-android10/android/prebuilts/clang/host/linux-x86/clang-r353983c/bin')
SOURCE = Path(__file__).with_suffix('.S')
PROPERTIES = ['roc_panel_profile', 'lcd_x', 'lcd_y', 'lcd_dclk_freq', 'lcd_hbp',
              'lcd_ht', 'lcd_hspw', 'lcd_vbp', 'lcd_vt', 'lcd_vspw',
              'lcd_hv_clk_phase', 'lcd_hv_sync_polarity']
VALUES = [[0,720,480,26,46,820,2,20,536,5,1,3],
          [1,640,480,24,46,770,20,15,520,4,2,3]]
LINKER = '''ENTRY(roc_early_after_environment)
SECTIONS {
 .early_bridge 0x4a026500 : { *(.early_bridge) }
 /DISCARD/ : { *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) }
 ASSERT(ADDR(.early_bridge) + SIZEOF(.early_bridge) <= 0x4a026afc, "early hook limit")
}
roc_initr_env = 0x4a00f175;
roc_env_get = 0x4a00e8f9;
roc_env_set = 0x4a00e621;
roc_original_workmode_display = 0x4a00297d;
roc_fdt_path_offset = 0x4a067fdd;
roc_fdt_getprop = 0x4a067e7d;
roc_fdt_get_one_gpio = 0x4a004455;
roc_gpio_request = 0x4a003e65;
roc_gpio_read_one = 0x4a003abd;
roc_udelay = 0x4a069a89;
'''


def require(value, why):
    if not value:
        raise ValueError(why)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def read_elf(path):
    blob = path.read_bytes()
    require(blob[:7] == b'\x7fELF\x01\x01\x01', 'ELF32 LE')
    require(struct.unpack_from('<HH', blob, 16) == (2,40), 'Executable ARM ELF')
    shoff, = struct.unpack_from('<I',blob,32)
    entsize,count,nsindex = struct.unpack_from('<HHH',blob,46)
    require(entsize == 40, 'ELF section stride')
    hs=[struct.unpack_from('<10I',blob,shoff+40*i) for i in range(count)]
    ns=blob[hs[nsindex][4]:hs[nsindex][4]+hs[nsindex][5]]
    allocated=[]; symbols={}
    for h in hs:
        name=ns[h[0]:ns.index(0,h[0])].decode()
        require(not(h[1] in (4,9) and h[5]), 'Unexpected unresolved ELF relocation')
        if h[2] & 2 and h[5]:
            require(name == '.early_bridge' and h[1] == 1 and h[3] == BASE+START,
                    'Unexpected allocated section')
            require(0 < h[5] <= LIMIT-START, 'Payload exceeds reclaimed driver cave')
            allocated.append(blob[h[4]:h[4]+h[5]])
        if h[1] == 2:
            st=hs[h[6]]; strings=blob[st[4]:st[4]+st[5]]
            for off in range(h[4],h[4]+h[5],h[9]):
                n,v,size,info,other,index=struct.unpack_from('<IIIBBH',blob,off)
                name=strings[n:strings.index(0,n)].decode()
                if name: symbols[name]=v
    require(len(allocated)==1, 'Exactly one hook section')
    return allocated[0],symbols


def patch_original(original, dispatched, payload, entry):
    ub.guard_original(original)
    require(sha(dispatched)==DISPATCH_SHA, 'Frozen complete panel dispatcher changed')
    require(original[0x2a20:0x2a24].hex()=='fff7acbf', 'Early display tail identity')
    require(original[0xf1be:0xf1c2].hex()=='f3f79dfd', 'Early logo call identity')
    require(struct.unpack_from('<I',original,0x9ee64)[0]==BASE+0xf175,
            'Actual initr_env callback identity')
    # No pre-existing dynamic relocation may point into the reclaimed payload.
    targets=[]
    for p in range(ub.RELDYN_START,ub.RELDYN_END,8):
        address,kind=struct.unpack_from('<II',original,p)
        require(kind==23, 'Original relocation type')
        off=address-BASE
        require(not START <= off < START+len(payload), 'Hook overwrites dynamic relocation target')
        targets.append(off)
    require(len(targets)==11978 and 0x9ee64 in targets, 'Actual init pointer relocation retained')
    changed=bytearray(dispatched)
    # Do not remove board_early_init_r: its clock setup precedes this tail.
    patches=[(0x2a20,bytes.fromhex('00207047'),'defer display tail after original clocks'),
             (0xf1be,bytes.fromhex('00bf00bf'),'defer early-logo call'),
             (0x9ee64,struct.pack('<I',entry),'replace env callback with import+profile+display wrapper'),
             (START,payload,'position-independent early bridge')]
    for off,data,_ in patches:
        changed[off:off+len(data)]=data
    require(changed[ub.RELDYN_START:ub.RELDYN_END]==original[ub.RELDYN_START:ub.RELDYN_END],
            'Original complete dynamic relocation table preserved')
    ranges=sorted((o,o+len(d)) for o,d,_ in patches)
    cursor=0
    for first,last in ranges:
        require(dispatched[cursor:first]==changed[cursor:first], 'Unexpected delta outside hooks')
        cursor=last
    require(dispatched[cursor:]==changed[cursor:], 'Unexpected suffix delta')
    return bytes(changed),[{'offset':o,'bytes':len(d),'role':role,'sha256':sha(d),
                          'before_sha256':sha(dispatched[o:o+len(d)])} for o,d,role in patches]


def execute(original, patched, symbols, *, env=None, samples=(1,)*5,
            descriptor='valid', request_ok=True, mux_input=True, slide=0,
            fdt_blob=None, null_fdt=False, env_result=0, early_clocks=False,
            fail_set=None):
    """Run final hook bytes + original libfdt and original GPIO read/MMIO code.

    Environment import/get/set, GPIO descriptor decode/request, display hardware
    and delay are API-boundary models. They clobber caller-saved registers.
    """
    import unicorn as uc
    from unicorn import arm_const as ar
    require(uc.__version__=='2.1.4', 'Pinned isolated Unicorn')
    env=dict(env or {})
    fdt_blob=FDT.read_bytes() if fdt_blob is None else bytes(fdt_blob)
    base=BASE+slide; sp0=0x4200ff00; fdt=0x48000000; strings=0x46000000
    gd=0x44000000; ret=0x41000000; handle=0x45000000
    cpu=uc.Uc(uc.UC_ARCH_ARM,uc.UC_MODE_THUMB)
    for address,size in [(base,0x100000),(0x42000000,0x10000),(gd,0x1000),
                         (fdt,(len(fdt_blob)+0xfff)&~0xfff),(ret,0x1000),
                         (strings,0x10000),(handle,0x1000),(0x0300b000,0x1000)]:
        cpu.mem_map(address,size)
    # Relocate every original cell, then transplant only the final bounded edits.
    relocated,relocation=ub._relocate_original_for_emulator(original,142,slide)
    image=bytearray(relocated)
    image[0x2a20:0x2a24]=patched[0x2a20:0x2a24]
    image[0xf1be:0xf1c2]=patched[0xf1be:0xf1c2]
    image[START:LIMIT]=patched[START:LIMIT]
    struct.pack_into('<I',image,0x9ee64,symbols['roc_early_after_environment']+slide)
    cpu.mem_write(base,bytes(image))
    cpu.mem_write(base+ub.WORKING_FDT_CELL,struct.pack('<I',0 if null_fdt else fdt))
    cpu.mem_write(fdt,fdt_blob)
    cpu.mem_write(handle,struct.pack('<I',1)+bytes(12)+b'gpios\0'+bytes(26)+
                  struct.pack('<6I',5,2,0,1,2,1)+bytes(16))
    cpu.mem_write(0x0300b090,struct.pack('<I',0 if mux_input else 0x100))
    cpu.mem_write(0x0300b0a0,struct.pack('<I',(samples[0]&1)<<2))
    # board_early_init_r uses its own global boot header pointer.
    cpu.mem_write(base,struct.pack('<I',0))
    cpu.mem_write(base+0xe0,struct.pack('<I',0))
    regs={i:getattr(ar,'UC_ARM_REG_R'+str(i)) for i in range(13)}
    saved={i:0x5a000000+i*0x1111 for i in range(4,12)}; saved[9]=gd
    for i,v in saved.items():cpu.reg_write(regs[i],v)
    cpu.reg_write(ar.UC_ARM_REG_SP,sp0);cpu.reg_write(ar.UC_ARM_REG_LR,ret|1)
    calls=[];sets={};reads=[];fdt_calls=[];sample_reads=[];next_string=0
    returned=[]

    def string(address):
        return bytes(cpu.mem_read(address,160)).split(b'\0',1)[0].decode('ascii')

    def clobber_return(value=0):
        target=cpu.reg_read(ar.UC_ARM_REG_LR)
        for i in (0,1,2,3,12):cpu.reg_write(regs[i],0x55aa0000+i)
        cpu.reg_write(regs[0],value&0xffffffff)
        cpu.reg_write(ar.UC_ARM_REG_APSR_NZCV,0xa0000000)
        cpu.reg_write(ar.UC_ARM_REG_PC,target)

    def api(address,size):
        nonlocal next_string
        if address==ret:
            returned.append(True);cpu.emu_stop();return
        off=address-base
        endpoints=(0xf174,0xe8f8,0xe620,0x297c,0x4454,0x3e64,0x69a88,0x16848)
        if off in endpoints:
            require(cpu.reg_read(ar.UC_ARM_REG_SP)%8==0,'Actual API stack alignment')
            require(cpu.reg_read(regs[9])==gd,'Reserved r9 changed')
        if off==0xf174:
            calls.append('import_environment');clobber_return(env_result);return
        if off==0xe8f8:
            name=string(cpu.reg_read(regs[0]));reads.append(name)
            value=env.get(name)
            if value is None:clobber_return(0)
            else:
                addr=strings+next_string;data=value.encode()+b'\0';next_string+=len(data)+4
                cpu.mem_write(addr,data);clobber_return(addr)
            return
        if off==0xe620:
            name,value=string(cpu.reg_read(regs[0])),string(cpu.reg_read(regs[1]))
            require(name in ('roc_active_model','roc_boot_route'),'Unexpected environment mutation')
            calls.append('set:'+name)
            if name == fail_set:
                clobber_return(1)
            else:
                sets[name]=value;clobber_return()
            return
        if off==0x297c:
            calls.append('display_after_profile')
            require(calls[0]=='import_environment' and len(sets)==2,'First display before profile/route')
            clobber_return();return
        if off==0x4454:
            require(string(cpu.reg_read(regs[0]))=='/soc@03000000/gpio_keys/keyvol-', 'Volume path ABI')
            require(string(cpu.reg_read(regs[1]))=='gpios','GPIO descriptor ABI')
            calls.append('volume_descriptor')
            if descriptor=='missing':clobber_return(-1)
            else:
                p=cpu.reg_read(regs[2]);cpu.mem_write(p,b'gpios\0'+bytes(26)+struct.pack('<6I',
                         5 if descriptor=='valid' else 4,2,7,0,2,1))
                clobber_return()
            return
        if off==0x3e64:
            p=cpu.reg_read(regs[0]);config=struct.unpack('<6I',bytes(cpu.mem_read(p+32,24)))
            require(config==(5,2,0,1,2,1) and cpu.reg_read(regs[1])==1,'Only PE2 input/pullup configured')
            calls.append('gpio_request');clobber_return(handle if request_ok else 0);return
        if off==0x69a88:
            require(cpu.reg_read(regs[0])==1000,'Debounce exactly1ms')
            calls.append('delay_1ms');clobber_return();return
        if off==0x3abc:
            require(cpu.reg_read(regs[0])==handle and cpu.reg_read(regs[1])==0,'Actual GPIO read ABI')
            k=min(len(sample_reads),len(samples)-1);sample_reads.append(samples[k])
            cpu.mem_write(0x0300b0a0,struct.pack('<I',(samples[k]&1)<<2))
        if off in (ub.FDT_PATH_OFFSET,ub.FDT_GETPROP):
            require(cpu.reg_read(ar.UC_ARM_REG_SP)%8==0,'Libfdt stack alignment')
            fdt_calls.append(off)
        if off==0x16848:
            calls.append('original_clk_init');clobber_return();return
        require((START<=off<LIMIT or 0x66b00<=off<0x68300 or 0x69800<=off<0x69b00 or
                 0x3a20<=off<0x3a4c or 0x3abc<=off<0x3b1a or
                 early_clocks and 0x2a04<=off<0x2a2c),
                'Execution outside final hook/proven actual helpers: '+hex(off))

    cpu.hook_add(uc.UC_HOOK_CODE,lambda m,a,s,u:api(a,s))
    entry=base+0x2a05 if early_clocks else symbols['roc_early_after_environment']+slide
    cpu.emu_start(entry,base+0x100000,timeout=10_000_000,count=3_000_000)
    require(returned==[True],'Bounded hook failed to return')
    require(cpu.reg_read(ar.UC_ARM_REG_SP)==sp0,'Hook SP not restored')
    require(all(cpu.reg_read(regs[i])==v for i,v in saved.items()),'Callee-saved registers changed')
    actual_fdt=bytes(cpu.mem_read(fdt,len(fdt_blob)))
    from h700_panel_profiles import fdt_properties,KEY
    _,props=fdt_properties(actual_fdt)
    panel='/soc@03000000/lcd0@01c0c000/'
    values=[]
    for name in PROPERTIES:
        item=props.get(panel+name)
        values.append(None if item is None or len(item['data'])!=4 else struct.unpack_from('>I',actual_fdt,item['offset'])[0])
    return {'env':env,'slide':slide,'sets':sets,'calls':calls,'env_reads':reads,
            'actual_gpio_read_samples':sample_reads,'actual_libfdt_calls':len(fdt_calls),
            'profile_values':values,'fdt_unchanged':actual_fdt==fdt_blob,
            'SP_callee_saved_r9':True,'r0':cpu.reg_read(regs[0]),
            'relocation_records':relocation['records_validated']}


def build(work,output):
    constrained()
    require(not work.exists() and not output.exists(),'Fresh build/output directory required')
    work.mkdir(parents=True);output.mkdir(parents=True)
    controls={str(p.relative_to(REPO)):sha(p.read_bytes()) for p in (Path(__file__),SOURCE)}
    result={'passed':False,'scope':'early U-Boot hook final-byte host execution only',
            'bridge_semantics_version':5,
            'physical_display_accepted':False,'automatic_identity':False,'controls':controls}
    write_json(output/'result.json',result)
    try:
        original=ORIGINAL.read_bytes();dispatched=DISPATCH.read_bytes()
        (work/'hook.S').write_bytes(SOURCE.read_bytes());(work/'hook.ld').write_text(LINKER)
        subprocess.run([str(CLANG/'clang.real'),'--target=armv7a-none-eabi','-mthumb','-march=armv7-a',
                        '-c','hook.S','-o','hook.o'],cwd=work,check=True)
        subprocess.run([str(CLANG/'ld.lld'),'-T','hook.ld','--no-undefined','--fatal-warnings',
                        '--build-id=none','-Map=hook.map','-o','hook.elf','hook.o'],cwd=work,check=True)
        payload,symbols=read_elf(work/'hook.elf')
        patched,patches=patch_original(original,dispatched,payload,symbols['roc_early_after_environment'])
        result.update(payload_bytes=len(payload),payload_sha256=sha(payload),patches=patches,
                      patched_sha256=sha(patched),symbols={k:hex(v) for k,v in symbols.items()})
        (output/'early-bridge.bin').write_bytes(payload)
        (output/'uboot.early-selector.bin').write_bytes(patched)
        (output/'early-bridge.elf').write_bytes((work/'hook.elf').read_bytes())
        disassembly=subprocess.check_output(['arm-linux-gnueabihf-objdump','-d',str(work/'hook.elf')],text=True)
        (output/'early-bridge.txt').write_text(disassembly)
        cases=[]
        def check(label, model,route,profile,**kwargs):
            row=execute(original,patched,symbols,**kwargs)
            require(row['sets']=={'roc_active_model':model,'roc_boot_route':route},label+' wrong route/model')
            require(row['profile_values']==VALUES[profile],label+' wrong full timing profile')
            require(row['r0']==0,label+' successful initcall returned an error')
            cases.append(dict(case=label,**row))
        for slide in (0,0x01000000):
            check('first_use_default35h640', 'rg35xxh','selector',1,slide=slide)
            check('empty_saved_is_first_use35h640','rg35xxh','selector',1,slide=slide,
                  env={'roc_saved_model':''})
            check('unsaved_hotkey_keeps_default35h640','rg35xxh','selector',1,
                  slide=slide,samples=(0,)*5)
            check('empty_saved_hotkey_keeps_default35h640','rg35xxh','selector',1,slide=slide,
                  env={'roc_saved_model':''},samples=(0,)*5)
            check('stray_next_model_is_first_use35h640','rg35xxh','selector',1,slide=slide,
                  env={'roc_next_model':'rg34xxsp'})
            for model,profile in [('rg34xxsp',0),('rgsp',0),('rg35xxh',1)]:
                check('saved_'+model,model,'start_saved',profile,slide=slide,
                      env={'roc_saved_model':model})
                check('saved_hotkey_'+model,model,'selector',profile,slide=slide,
                      env={'roc_saved_model':model},samples=(0,)*5)
                check('next_'+model,model,'start_once',profile,slide=slide,
                      env={'roc_saved_model':'rgsp','roc_next_start':'1','roc_next_model':model})
                check('next_hotkey_'+model,model,'selector',profile,slide=slide,
                      env={'roc_saved_model':'rgsp','roc_next_start':'1','roc_next_model':model},
                      samples=(0,)*5)
                check('next_model_without_flag_'+model,model,'start_saved',profile,slide=slide,
                      env={'roc_saved_model':model,'roc_next_model':'rg35xxh'})
                # The hotkey must change only the route, never the model/timings.
                plain=cases[-5];held=cases[-4]
                require(plain['profile_values']==held['profile_values'] and
                        plain['sets']['roc_active_model']==held['sets']['roc_active_model'],
                        'Saved hotkey changed the resolved panel/model')
                plain=cases[-3];held=cases[-2]
                require(plain['profile_values']==held['profile_values'] and
                        plain['sets']['roc_active_model']==held['sets']['roc_active_model'],
                        'One-time hotkey changed the resolved panel/model')
            for bad in ('1x','0','', '01'):
                check('bad_next_flag_'+repr(bad),'rg34xxsp','selector',0,slide=slide,
                      env={'roc_next_start':bad,'roc_next_model':'rg35xxh','roc_saved_model':'rgsp'},samples=(0,)*5)
            for bad in ('rg34xx','rg35xxsp','rg35xxh-extra','RG35XXH',''):
                check('bad_next_model_'+repr(bad),'rg34xxsp','selector',0,slide=slide,
                      env={'roc_next_start':'1','roc_next_model':bad,'roc_saved_model':'rgsp'},samples=(0,)*5)
            check('missing_next_model_keeps_strict_default','rg34xxsp','selector',0,slide=slide,
                  env={'roc_next_start':'1','roc_saved_model':'rg35xxh'},samples=(0,)*5)
            check('bad_saved_hotkey_keeps_default','rg34xxsp','selector',0,slide=slide,
                  env={'roc_saved_model':'cubexx'},samples=(0,)*5)
            for bad in ('rg34xx','rg35xxsp','rg35xxh-extra','RG35XXH',' '):
                check('bad_nonempty_saved_'+repr(bad),'rg34xxsp','selector',0,slide=slide,
                      env={'roc_saved_model':bad})
            check('valid_once_overrides_bad_saved','rg35xxh','start_once',1,slide=slide,
                  env={'roc_next_start':'1','roc_next_model':'rg35xxh','roc_saved_model':'cubexx'})
            for desc in ('missing','wrong_port'):
                check('bad_gpio_'+desc,'rg35xxh','selector',1,slide=slide,descriptor=desc,samples=(0,)*5)
            check('request_failed','rg35xxh','selector',1,slide=slide,request_ok=False,samples=(0,)*5)
            check('noninput_mux','rg35xxh','selector',1,slide=slide,mux_input=False,samples=(0,)*5)
            check('saved35h_missing_gpio_keeps_saved','rg35xxh','start_saved',1,slide=slide,
                  env={'roc_saved_model':'rg35xxh'},descriptor='missing',samples=(0,)*5)
            check('next35h_failed_request_keeps_once','rg35xxh','start_once',1,slide=slide,
                  env={'roc_next_start':'1','roc_next_model':'rg35xxh'},request_ok=False,samples=(0,)*5)
            for sample in range(5):
                values=[0]*5;values[sample]=1
                check('bounce_'+str(sample),'rg35xxh','selector',1,slide=slide,samples=values)
                check('saved35h_bounce_'+str(sample),'rg35xxh','start_saved',1,slide=slide,
                      env={'roc_saved_model':'rg35xxh'},samples=values)
                check('next35h_bounce_'+str(sample),'rg35xxh','start_once',1,slide=slide,
                      env={'roc_next_start':'1','roc_next_model':'rg35xxh'},samples=values)
            # Property failures must precede every timing write.
            from h700_panel_profiles import fdt_properties
            normal=bytearray(FDT.read_bytes());_,props=fdt_properties(normal)
            for name in PROPERTIES:
                altered=bytearray(normal);p=props['/soc@03000000/lcd0@01c0c000/'+name]['offset']
                struct.pack_into('>I',altered,p-8,3)
                row=execute(original,patched,symbols,slide=slide,fdt_blob=altered,
                            env={'roc_next_start':'1','roc_next_model':'rg35xxh'})
                require(row['sets']=={'roc_active_model':'rg34xxsp','roc_boot_route':'selector'} and
                        row['fdt_unchanged'],'Partial FDT write on invalid property '+name)
                cases.append(dict(case='short_property_'+name,**row))
            row=execute(original,patched,symbols,slide=slide,null_fdt=True,
                        env={'roc_saved_model':'rg35xxh'})
            require(row['fdt_unchanged'] and row['sets']['roc_active_model']=='rg34xxsp','Null FDT fallback')
            cases.append(dict(case='null_fdt',**row))
            row=execute(original,patched,symbols,slide=slide,null_fdt=True)
            require(row['fdt_unchanged'] and
                    row['sets']=={'roc_active_model':'rg34xxsp','roc_boot_route':'selector'},
                    'First-use null FDT did not retain original720 error route')
            cases.append(dict(case='first_use_null_fdt',**row))
            missing_panel=bytes(normal).replace(b'lcd0@01c0c000\0',b'lcd9@01c0c000\0',1)
            require(missing_panel!=bytes(normal),'Missing-panel negative fixture did not change')
            row=execute(original,patched,symbols,slide=slide,fdt_blob=missing_panel)
            require(row['fdt_unchanged'] and
                    row['sets']=={'roc_active_model':'rg34xxsp','roc_boot_route':'selector'},
                    'First-use missing LCD node did not retain original720 error route')
            cases.append(dict(case='first_use_missing_panel_node',**row))
            row=execute(original,patched,symbols,slide=slide,env_result=9)
            require(not row['sets'] and row['calls']==['import_environment'] and row['r0']==9,'Original env failure semantics')
            cases.append(dict(case='environment_failure',**row))
            for fail_set in ('roc_active_model','roc_boot_route'):
                row=execute(original,patched,symbols,slide=slide,fail_set=fail_set,
                            env={'roc_saved_model':'rg35xxh'})
                require(row['r0']==1 and 'display_after_profile' not in row['calls'],
                        'Setter failure must stop before display/initcall continuation')
                require(row['profile_values']==VALUES[1], 'Setter failure case did not select requested full profile')
                require(row['sets']==({} if fail_set=='roc_active_model' else {'roc_active_model':'rg35xxh'}),
                        'Unexpected successful mutations in failed setter case')
                cases.append(dict(case='setter_failure_'+fail_set,**row))
            row=execute(original,patched,symbols,slide=slide,early_clocks=True)
            require(row['calls']==['original_clk_init'] and not row['sets'],'Original clocks were removed/display not deferred')
            cases.append(dict(case='clocks_retained_display_deferred',**row))
        require(all(sha((REPO/path).read_bytes())==value for path,value in controls.items()),'Inputs mutated during build')
        write_json(output/'execution.json',{'passed':True,'cases':cases})
        result.update(passed=True,host_cases=len(cases),execution_sha256=sha((output/'execution.json').read_bytes()),
                      supported_profiles=['retained720 rg34xxsp/rgsp','35H profile1'],
                      actual_libfdt=True,actual_gpio_read=True,all_original_relocations=11978,
                      early_clock_init_preserved=True,first_display_after_environment=True,
                      persistent_environment_writes=False,
                      unsaved_route='selector',unsaved_model='rg35xxh',unsaved_profile='35H640',
                      empty_saved_is_first_use=True,invalid_nonempty_saved='retained720_selector',
                      hotkey_changes_route_only=True,
                      invalid_present_once_request='default720_selector',
                      automatic_profile_probe=False)
        print(json.dumps(result),flush=True)
    except Exception as error:
        result['error']=repr(error)
        raise
    finally:
        write_json(output/'result.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build(args.work,args.output)
