#!/usr/bin/env python3
"""Prepare isolated Android 10 ARM64 runtime; never deploy or mount on a device."""
from pathlib import Path
import zipfile,subprocess,json,shutil,hashlib
from package_h700_v6a import constrained,sha,dump
from android_sparse_to_raw import convert
constrained()
root=Path(__file__).resolve().parents[1];out=root/'out/arm64-isolated-20261030'
work=Path('/home/lpf/h700-arm64-isolated-20261030');work.mkdir(exist_ok=True)
archive=out/'aosp_arm64-exp-QJR1.191112.001-6004257.zip'
assert archive.stat().st_size==597613423
assert sha(archive)=='0bbbf53e1164b032eace999cbd6bf0877ab636819a2e929f63079ccfe71095c7'
print('GSI_ZIP_SHA256',sha(archive),flush=True)
with zipfile.ZipFile(archive) as z:
 print('GSI_ZIP_MEMBERS',[(n,z.getinfo(n).file_size) for n in z.namelist()],flush=True)
 member=next(n for n in z.namelist() if n.endswith('system.img'))
 packed=work/'gsi-system.img';raw=work/'gsi-system.raw'
 if not packed.exists():
  with z.open(member) as src,packed.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024)
 if not raw.exists():
  with packed.open('rb') as f:magic=f.read(4)
  if magic==bytes.fromhex('3aff26ed'):convert(str(packed),str(raw))
  else:subprocess.run(['cp','--sparse=always',str(packed),str(raw)],check=True)

import re
source=Path('/home/lpf/h700-android10/android')
stage=out/'runtime';libdir=stage/'lib64';libdir.mkdir(parents=True,exist_ok=True)
loader=dump(raw,'/system/bin/bootstrap/linker64',stage/'linker64');loader.chmod(0o755)
prop=dump(raw,'/system/build.prop',out/'gsi-build.prop');assert 'ro.build.version.sdk=29' in prop.read_text()
assert sha(archive)=='0bbbf53e1164b032eace999cbd6bf0877ab636819a2e929f63079ccfe71095c7'
mali=source/'hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so'
assert sha(mali)==json.loads((root/'out/arm64-feasibility-20261030/offline-audit.json').read_text())['libraries'][2]['sha256']
shutil.copyfile(mali,libdir/mali.name)
def needed(p):
 return re.findall(r'Shared library: \[(.*?)\]',subprocess.check_output(['readelf','-d',str(p)],text=True))
queue=needed(mali);receipt={};dirs=['/system/lib64/bootstrap','/system/apex/com.android.runtime.release/lib64/bionic','/system/apex/com.android.runtime.release/lib64','/system/lib64','/system/lib64/vndk-sp-29','/system/lib64/vndk-29']
while queue:
 name=queue.pop(0)
 if name in receipt:continue
 assert '/' not in name and '..' not in name
 dest=libdir/name;found=None
 for directory in dirs:
  try:
   dump(raw,directory+'/'+name,dest)
   if dest.read_bytes()[:5]!=b'\x7fELF\x02':continue
   found=directory+'/'+name;break
  except (OSError,ValueError):pass
 if not found:raise ValueError('Missing ELF64 dependency '+name)
 receipt[name]={'source':found,'sha256':sha(dest),'needed':needed(dest)};queue.extend(receipt[name]['needed'])
ndk=source/'prebuilts/ndk/r18';platform=ndk/'platforms/android-28/arch-arm64/usr/lib';clang=source/'prebuilts/clang/host/linux-x86/clang-r353983c/bin/clang.real';builtins=source/'prebuilts/clang/host/linux-x86/clang-r353983c/lib64/clang/9.0.3/lib/linux/libclang_rt.builtins-aarch64-android.a'
args=[str(clang),'--target=aarch64-linux-android28','--sysroot='+str(ndk/'sysroot'),'-isystem',str(ndk/'sysroot/usr/include/aarch64-linux-android'),'-fuse-ld=lld','-fPIE','-pie','-nostdlib',str(platform/'crtbegin_dynamic.o'),str(root/'tools/arm64_probe/isolated_egl.c'),'-L'+str(platform),str(libdir/'libc.so'),str(libdir/'libdl.so'),str(builtins),str(platform/'crtend_android.o'),'-Wl,--dynamic-linker=/data/local/tmp/h700-arm64-isolated-20261030/linker64','-o',str(stage/'probe')]
args[1:1]=sum((['-isystem',str(source/p)] for p in ['bionic/libc/include','bionic/libc/kernel/uapi/asm-arm64','bionic/libc/kernel/uapi','bionic/libc/kernel/android/uapi','frameworks/native/opengl/include']),[])
subprocess.run(args,check=True)
probe_needed=needed(stage/'probe');assert 'libc.so' in probe_needed and 'libdl.so' in probe_needed,probe_needed
direct=args[:];direct[1:1]=['-DDIRECT_MALI'];direct[-1]=str(stage/'probe-linked');direct[-2:-2]=['-Wl,--no-as-needed',str(libdir/'libGLES_mali.so'),'-Wl,--allow-shlib-undefined'];subprocess.run(direct,check=True)
subprocess.run([str(clang),'--target=aarch64-linux-android29','-fuse-ld=lld','-nostdlib','-static','-fno-builtin','-Wl,-e,_start',str(root/'tools/arm64_probe/mount_guard.c'),'-o',str(stage/'mount64')],check=True)
for f in [loader,stage/'probe',*libdir.glob('*')]:
 assert f.read_bytes()[:5]==b'\x7fELF\x02',f
manifest={'gsi_url':'https://dl.google.com/developers/android/qt/images/gsi/'+archive.name,'gsi_sha256':sha(archive),'api':29,'runtime_dependencies':receipt,'files':{f.relative_to(stage).as_posix():sha(f) for f in stage.rglob('*') if f.is_file()}}
(out/'runtime-lock.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('ISOLATED_RUNTIME_READY',len(receipt),'libraries',flush=True)

# Reproducible, minimal chroot payload. The source image's ld-android.so is a
# link-only stub; the running linker provides that SONAME, so do not deploy it.
rootfs=out/'prepared-rootfs'
if rootfs.exists():raise ValueError('Prepared rootfs already exists; preserve and inspect it')
for d in ['system/bin','system/lib64','system/etc','apex/com.android.runtime/bin','apex/com.android.runtime/lib64/bionic','dev/__properties__','proc','sys','data/local/tmp/h700-arm64-isolated-20261030']:
 (rootfs/d).mkdir(parents=True,exist_ok=True)
for f in libdir.glob('*.so'):
 if f.name!='ld-android.so':shutil.copyfile(f,rootfs/'system/lib64'/f.name)
for n in ['libc.so','libdl.so','libm.so']:shutil.copyfile(libdir/n,rootfs/'apex/com.android.runtime/lib64/bionic'/n)
for n in ['system/bin/linker64','apex/com.android.runtime/bin/linker64','data/local/tmp/h700-arm64-isolated-20261030/linker64']:shutil.copyfile(stage/'linker64',rootfs/n)
for n in ['probe','probe-linked']:shutil.copyfile(stage/n,rootfs/'system/bin'/n)
(rootfs/'system/etc/ld.config.txt').write_text('dir.default = /system/bin\n[default]\nnamespace.default.isolated = false\nnamespace.default.search.paths = /system/lib64:/apex/com.android.runtime/lib64/bionic\n')
for n in ['null','zero','urandom','random','ashmem','binder','hwbinder','vndbinder','mali0','ion']:(rootfs/'dev'/n).touch()
shutil.copyfile(root/'tools/arm64_probe/namespace_run.sh',out/'prepared-namespace-run.sh')
print('MINIMAL_CHROOT_PREPARED',flush=True)
