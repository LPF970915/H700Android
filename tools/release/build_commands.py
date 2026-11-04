"""Save the current Ninja rebuild command plan without executing commands."""
from pathlib import Path
import hashlib,json,subprocess,os
from package_h700_v6a import constrained
constrained()
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'out/source64-release-prep-20261104';work=next(out/('commands-v%d'%n) for n in range(1,100) if not (out/('commands-v%d'%n)).exists());work.mkdir()
native=Path('/home/lpf/h700-android10/android');build=Path('/home/lpf/roc-os-source64-20261103/out');ninja=native/'prebuilts/build-tools/linux-x86/bin/ninja';graph=build/'combined-roc_os_source64.ninja';target=build/'target/product/roc_os_source64'
with (work/'commands.private.txt').open('xb') as stream:
 result=subprocess.run([str(ninja),'-f',str(graph),'-t','commands',*[str(target/x) for x in ['system.img','vendor.img','ramdisk.img']]],cwd=native,stdout=stream,stderr=subprocess.PIPE)
(work/'stderr.txt').write_bytes(result.stderr);assert result.returncode==0,result.stderr
h=hashlib.sha256();count=0;external=[];needles=[b'device/linaro/bootloader/edk2/EmulatorPkg/Unix/Host/X11IncludeHack',b'external/e2fsprogs/config/ltmain.sh']
found={x.decode():False for x in needles}
with (work/'commands.private.txt').open('rb') as stream:
 for line in stream:
  h.update(line);count+=1
  for x in needles:
   if x in line:found[x.decode()]=True
for name in needles:
 path=native/name.decode();resolved=path.resolve(strict=False);d={'source_symlink':name.decode(),'recorded_target':os.readlink(path),'exists':resolved.exists(),'command_literal_reference':found[name.decode()]}
 if resolved.is_file():
  with resolved.open('rb') as stream:d['external_file_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
 external.append(d)
report={'commands':count,'commands_sha256':h.hexdigest(),'bytes':(work/'commands.private.txt').stat().st_size,'targets':['system.img','vendor.img','ramdisk.img'],'ninja_version':subprocess.check_output([str(ninja),'--version'],text=True).strip(),'graph':{},'external_symlinks':external,'scope':'read-only rebuild command plan; not execution history or complete upstream repo manifest','commands_executed':False}
for f in [graph,build/'build-roc_os_source64.ninja',build/'soong/build.ninja']:
 with f.open('rb') as stream:report['graph'][f.name]=hashlib.file_digest(stream,'sha256').hexdigest()
(work/'result.json').write_text(json.dumps(report,indent=2)+'\n');(out/'latest-commands.json').write_text(json.dumps({'work':str(work)})+'\n');print(json.dumps(report),flush=True)
