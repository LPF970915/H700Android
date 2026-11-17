"""Exercise generated real boot environment routes as simple-parser commands.

Only a bounded parent environment range from an ordinary prefix is read. The
interpreter checks generated route behavior; it is not hardware acceptance.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shlex
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools/release'),str(ROOT/'tools')]
import h700_manual_selector_twelve as manual
from h700_panel_boot import decode_env,ENV_OFFSET,ENV_SIZE
from models import ALL_MODEL_IDS,MODEL_PROFILE,MODEL_METADATA,TIMINGS,PROPERTIES


def run(commands, model, route):
    env=dict(commands,roc_active_model=model,roc_boot_route=route,bootargs='console=ttyS0')
    fdt={};calls=[];booted=False
    def expand(value):
        return re.sub(r'\$\{([^}]+)\}',lambda m:env.get(m[1],''),value)
    def command(name,depth=0):
        nonlocal booted
        assert depth<12, 'Unexpected recursive run'
        words=shlex.split(expand(env[name]));calls.append(name)
        assert words and not any(x in env[name] for x in (';','&&','\n'))
        if words[0]=='run':
            for nested in words[1:]:command(nested,depth+1)
        elif words[0]=='sunxi_flash':assert words==['sunxi_flash','read','45000000','boot']
        elif words[:2]==['fdt','addr']:assert env[name]=='fdt addr ${fdtcontroladdr}'
        elif words[:2]==['fdt','set']:
            assert words[2]==manual.PANEL and len(words)==5
            fdt[words[3]]=int(words[4][1:-1],16)
        elif words[0]=='setenv':env[words[1]]=' '.join(words[2:])
        elif words[0]=='bootm':assert words==['bootm','45000000'];booted=True
        else:raise AssertionError(words)
    # Actual Test7 control-FDT token must be preserved during variable expansion.
    env['fdtcontroladdr']='44000000'
    command('boot_normal')
    assert booted
    profile=MODEL_PROFILE[model];metadata=MODEL_METADATA[model]
    assert fdt=={'roc_panel_profile':profile,**TIMINGS[profile]}
    args=dict(token.split('=',1) for token in env['bootargs'].split())
    expected={'roc_model':model,'roc_clamshell':str(int(metadata['lid'])),
              'roc_route':route,'roc_sticks':str(metadata['sticks']),
              'roc_form_factor':metadata['form_factor'],
              'roc_native_width':str(metadata['native_size'][0]),
              'roc_native_height':str(metadata['native_size'][1]),
              'roc_rotation':str(metadata['display_rotation']),
              'roc_panel_profile':str(profile)}
    for key,value in expected.items():assert args['androidboot.'+key]==value,(model,key,args)
    return {'model':model,'route':route,'panel_profile':profile,'calls':calls,
            'fdt':fdt,'bootargs':env['bootargs']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prefix',type=Path,default=Path('/home/lpf/roc-os-h700-shared-panel-20261114-v1/prefix.shared.raw'))
    args=parser.parse_args()
    assert not args.output.exists();args.output.mkdir(parents=True)
    with args.prefix.open('rb') as stream:
        stream.seek(ENV_OFFSET);parent=stream.read(ENV_SIZE)
    changed,receipt=manual.patch_environment(parent,0x1200000)
    decoded=dict(decode_env(changed));original=dict(decode_env(parent))
    assert len(decoded)<256 and len(changed)==ENV_SIZE
    commands=manual.kernel_commands(0x1200000)
    assert {k:v for k,v in decoded.items() if k not in commands}=={
        k:v for k,v in original.items() if k not in commands}
    rows=[run(commands,model,route) for model in ALL_MODEL_IDS
          for route in ('selector','start_once','start_saved')]
    catalog=json.loads((ROOT/'out/boot-selector-integration-20261114/panel-catalog/catalog.json').read_text())
    for model,source in catalog['profiles'].items():
        values=source['nodes']['lcd0@01c0c000']
        actual={name:values[name]['u32'][0] for name in PROPERTIES[1:]}
        assert TIMINGS[MODEL_PROFILE[model]]==actual,(model,actual)
    report={'passed':True,'cases':len(rows),'rows':rows,'environment_rows':len(decoded),
            'environment_before_sha256':hashlib.sha256(parent).hexdigest(),
            'environment_after_sha256':hashlib.sha256(changed).hexdigest(),
            'scope':'generated simple-parser boot routing only; not physical acceptance',
            'all12_explicit':True,'ram_gate':False,
            'plus2025_shared_reference_unverified':True,'rotation28xx_physical_unverified':True}
    (args.output/'environment.fixture.bin').write_bytes(changed)
    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__=='__main__':main()
