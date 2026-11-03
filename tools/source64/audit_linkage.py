"""ELF interpreter and namespace closure for offline source64 partitions."""
from pathlib import Path
import json, re, subprocess, posixpath, struct, hashlib


def audit(w, run, file):
    images={'system': w/'system.raw', 'vendor': w/'vendor.raw'}
    stats={}; dumps={}; errors=[]; graph={}; elfs={}
    for part, name in [('system', '/system/etc/init'), ('vendor', '/etc/init')]:
        dest=w/'init-catalog'/part
        dest.mkdir(parents=True)
        run(['/usr/sbin/debugfs', '-R', 'rdump '+name+' '+str(dest), images[part]])
    ld=file('/system/etc/ld.config.29.txt').read_text();sections={}
    for match in re.finditer(r'^\[(.+?)\]\s*$(.*?)(?=^\[|\Z)',ld,re.M|re.S):
     opts={}
     for line in match[2].splitlines():
      m=re.match(r'([\w.]+)\s*(\+?=)\s*(.*)',line)
      if m:opts[m[1]]=(opts.get(m[1],'')+(':' if opts.get(m[1]) else '')+m[3]) if m[2]=='+=' else m[3]
     sections[match[1]]=opts

    def physical(path):
     if path.startswith('/vendor/'):return 'vendor',path[7:]
     return 'system',path

    def resolve(path,pre=False):
     seen=set()
     for _ in range(15):
      if path in seen:return None
      seen.add(path)
      if path.startswith('/apex/'):
       if pre:return None
       m=re.match(r'/apex/([^/]+)/(.*)',path)
       if not m:return None
       name=m[1];name='com.android.runtime.release' if name=='com.android.runtime' else name;path='/system/apex/'+name+'/'+m[2]
      if path.startswith('/odm/'):path='/vendor/odm/'+path[5:]
      part,inside=physical(path);key=(part,inside)
      if key not in stats:
       r=subprocess.run(['/usr/sbin/debugfs','-R','stat '+inside,str(images[part])],capture_output=True,text=True);stats[key]=r.stdout
      s=stats[key]
      if 'Type: regular' in s:return path
      m=re.search(r'Fast link dest: "([^"]+)"',s)
      if not m:return None
      path=posixpath.normpath(m[1] if m[1].startswith('/') else posixpath.dirname(path)+'/'+m[1])
     return None

    def dump(path):
     if path in dumps:return dumps[path]
     part,inside=physical(path);p=w/'elf'/part/inside.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);r=subprocess.run(['/usr/sbin/debugfs','-R','dump '+inside+' '+str(p),str(images[part])],capture_output=True,text=True);assert p.is_file(),(path,r.stderr);dumps[path]=p;return p

    def elf(path):
     if path in elfs:return elfs[path]
     f=dump(path);d=f.read_bytes();assert d[:4]==b'\x7fELF',path;r=subprocess.run(['readelf','-d','-l',str(f)],capture_output=True,text=True);assert r.returncode==0
     needed=re.findall(r'Shared library: \[(.*?)\]',r.stdout);m=re.search(r'interpreter: (.*?)\]',r.stdout);elfs[path]=dict(ELF_class=d[4],e_machine=struct.unpack_from('<H',d,18)[0],needed=needed,interpreter=m[1] if m else None,sha256=hashlib.sha256(d).hexdigest(),bytes=len(d));return elfs[path]

    def provider(section,ns,name,bits,visited=None):
     visited=set() if visited is None else visited
     if ns in visited:return None
     visited.add(ns);opts=sections[section];search=opts.get('namespace.'+ns+'.search.paths','').replace('${LIB}','lib64' if bits==2 else 'lib').replace('${VNDK_VER}','29')
     for directory in search.split(':'):
      p=resolve(directory+'/'+name)
      if p:return (ns,p)
     for dest in opts.get('namespace.'+ns+'.links','').split(','):
      dest=dest.strip()
      if not dest:continue
      libs=opts.get('namespace.'+ns+'.link.'+dest+'.shared_libs','').split(':');allow=opts.get('namespace.'+ns+'.link.'+dest+'.allow_all_shared_libs','')=='true'
      if name in libs or allow:
       found=provider(section,dest,name,bits,visited)
       if found:return found
     return None
    roots=['/system/bin/init','/system/bin/adbd','/system/bin/servicemanager','/system/bin/hwservicemanager','/system/bin/surfaceflinger','/system/bin/vold.rocsource','/system/bin/netd','/system/bin/audioserver','/system/bin/app_process64','/system/bin/app_process32','/system/bin/displayservice','/vendor/bin/vndservicemanager']
    for f in (w/'init-catalog/vendor').rglob('*.rc'):
     roots+=re.findall(r'^service\s+\S+\s+(/vendor/bin/hw/\S+)',f.read_text(),re.M)
    for bits in ['lib64','lib']:
     roots+=['/vendor/'+bits+'/egl/libGLES_mali.so','/vendor/'+bits+'/hw/gralloc.rocsource.so','/vendor/'+bits+'/hw/hwcomposer.cupid.so','/vendor/'+bits+'/hw/audio.primary.cupid.so','/vendor/'+bits+'/hw/android.hardware.graphics.mapper@2.0-impl-2.1.so']
    roots=list(dict.fromkeys(roots));queue=[]
    for root in roots:
     p=resolve(root)
     if not p:errors.append(dict(kind='root_missing',path=root));continue
     section='vendor' if root.startswith('/vendor/') else 'system';queue.append((section,'default',p))
    seen=set()
    while queue:
     section,ns,p=queue.pop(0);key=(section,ns,p)
     if key in seen:continue
     seen.add(key);v=elf(p);keystr='|'.join(key);graph[keystr]=[]
     if v['e_machine'] != {1: 40, 2: 183}.get(v['ELF_class']):
      errors.append(dict(kind='non_ARM_ELF',path=p,elf_class=v['ELF_class'],machine=v['e_machine']))
     if v['interpreter'] and not resolve(v['interpreter']):errors.append(dict(kind='interpreter_missing',path=p,interpreter=v['interpreter']))
     for name in v['needed']:
      found=provider(section,ns,name,v['ELF_class'])
      if not found:errors.append(dict(kind='namespace_dependency_unresolved',section=section,namespace=ns,path=p,library=name));continue
      owner,child=found;vv=elf(child)
      if vv['ELF_class']!=v['ELF_class']:errors.append(dict(kind='wrong_elf_class',path=p,library=child))
      graph[keystr].append(owner+':'+child);queue.append((section,owner,child))
    # Pre-apex init uses bootstrap linker; audit only the actual bootstrap search paths.
    bootstrap_dirs=['/system/lib64/bootstrap','/system/lib64'];pre_queue=['/system/bin/init'];pre_seen=set();pre_errors=[]
    while pre_queue:
     path=pre_queue.pop(0)
     if path in pre_seen:continue
     pre_seen.add(path);v=elf(path)
     for name in v['needed']:
      found=next((p for directory in bootstrap_dirs if (p:=resolve(directory+'/'+name,pre=True))),None)
      if not found:pre_errors.append(dict(path=path,library=name))
      else:pre_queue.append(found)
    # New daemons: also check strong undefined symbol names against their actual
    # resolved dependency scopes. Symbol versions/dlopen remain separate limits.
    symbols = {}
    def dynsymbols(path):
        if path not in symbols:
            listing = run(['readelf', '--dyn-syms', '--wide', dump(path)]).stdout
            exports, imports = set(), set()
            for line in listing.splitlines():
                fields = line.split()
                if len(fields) < 8 or not fields[0].endswith(':'):
                    continue
                bind, visibility, index, name = fields[4:8]
                name = name.split('@')[0]
                if index == 'UND' and bind == 'GLOBAL':
                    imports.add(name)
                elif index != 'UND' and bind in ('GLOBAL', 'WEAK') and visibility in ('DEFAULT', 'PROTECTED'):
                    exports.add(name)
            symbols[path] = exports, imports
        return symbols[path]
    strong_checks = {}
    for root in ['/system/bin/vold.rocsource', '/vendor/bin/hw/android.hardware.light@2.0-service.rocsource']:
        section = 'vendor' if root.startswith('/vendor/') else 'system'
        todo = [section + '|default|' + root]
        scope = set()
        while todo:
            key = todo.pop()
            if key in scope:
                continue
            scope.add(key)
            for edge in graph.get(key, []):
                owner, path = edge.split(':', 1)
                todo.append(section + '|' + owner + '|' + path)
        exports = set()
        for key in scope:
            exports.update(dynsymbols(key.split('|', 2)[2])[0])
        unresolved = sorted(dynsymbols(root)[1] - exports)
        strong_checks[root] = {'dependency_states': len(scope), 'unresolved_strong_symbol_names': unresolved}
        if unresolved:
            errors.append({'kind': 'new_daemon_strong_symbols', 'path': root, 'symbols': unresolved})
    res=dict(roots=roots,root_count=len(roots),namespace_object_states=len(seen),unique_ELF_objects=len(elfs),errors=errors,pre_apex_bootstrap_objects=len(pre_seen),pre_apex_bootstrap_errors=pre_errors,new_daemon_strong_symbols=strong_checks,notes=['DT_NEEDED and interpreter/ELF checks plus new-daemon symbol names; not exported symbol versions, dlopen completeness, kernel ABI or runtime acceptance','APEX runtime paths resolved to flattened directories for post-APEX audit; early bootstrap checked separately'],objects=elfs,graph=graph)
    return res
