"""Read actual Source64 audit snapshots and fail closed at release gates."""
import hashlib,json,re
from pathlib import Path
POLICY=json.loads(Path(__file__).with_name('release-policy.json').read_text())
def evaluate(props,rc,cmdline,certified=False,evidence=None):
 checks={k:props.get(k)==v for k,v in POLICY['properties'].items()}
 checks['user_build']=props.get('ro.build.type')==POLICY['build_type']
 checks['no_test_keys']=bool(props.get('ro.build.tags')) and not any(x in props['ro.build.tags'] for x in POLICY['forbidden_build_tags'])
 checks['no_TCP_ADB']=all(props.get(k,'-1') in ['-1','0',''] for k in ['service.adb.tcp.port','persist.adb.tcp.port'])
 checks['no_su_domain']=not bool(re.search(r'\bu:r:su:', '\n'.join(x.split('#',1)[0] for x in rc.splitlines())))
 checks['no_root_console']=not bool(re.search(r'^service\s+console\b|^service\s+\S+\s+/(?:system/)?bin/sh\s*$|^\s*console\s*$',rc,re.M))
 checks['boot_contract_provided']=cmdline is not None
 checks['no_permissive_boot']=cmdline is not None and not re.search(r'(?:androidboot\.)?selinux=permissive\b|\benforcing=0\b|\bselinux=0\b',cmdline)
 checks['private_signing_verified']=certified is True
 for name in POLICY['required_evidence']:checks[name]=(evidence or {}).get(name) is True
 return {'release_allowed':all(checks.values()),'checks':checks,'blockers':[k for k,v in checks.items() if not v]}
def snapshot(work):
 work=Path(work);meta=json.loads((work/'files.json').read_text());props={};loaded=[]
 def load(name):
  spec=meta.get(name)
  if spec is None:raise ValueError('Unproven property file presence: '+name)
  if not spec['exists']:return
  part,rel=('vendor',name[7:]) if name.startswith('/vendor/') else ('system',name)
  p=work/'files'/part/rel.lstrip('/');content=p.read_bytes()
  if hashlib.sha256(content).hexdigest()!=spec['sha256']:raise ValueError('Audited property file changed')
  loaded.append(name)
  for line in content.decode().splitlines():
   line=line.strip()
   if line.startswith('import '):raise ValueError('Unresolved property import')
   if line and not line.startswith('#') and '=' in line:
    k,v=line.split('=',1);props[k.strip()]=v.strip()
 default=next((x for x in ['/system/etc/prop.default','/prop.default','/default.prop'] if meta.get(x,{}).get('exists')),None)
 if not default:raise ValueError('No audited default properties')
 load(default)
 for x in ['/system/build.prop','/vendor/default.prop','/vendor/build.prop']:load(x)
 odm=['/vendor/odm/etc/build.prop'] if int(props.get('ro.vendor.build.version.sdk','0'))>=29 else ['/vendor/odm/default.prop','/vendor/odm/build.prop']
 for x in odm+['/system/product/build.prop','/system/product_services/build.prop']:
  # Missing snapshot coverage fails closed; never silently assume absent.
  load(x)
 rc='\n'.join(p.read_text() for p in sorted((work/'init-catalog').rglob('*.rc')))
 return props,rc,loaded

def signing_allowed(signers, registry, test_fingerprints):
    required = ['SystemUI','Settings','ROCNavigation','H700Lid','H700Rotation','AT4K']
    platform = registry.get('platform_sha256','').lower()
    if not re.fullmatch('[0-9a-f]{64}',platform) or platform in test_fingerprints:
        return False
    if any(signers.get(name)!=[platform] for name in required):
        return False
    allowed=registry.get('presigned_certificates',{})
    return all(values==[platform] or values==allowed.get(name) for name,values in signers.items())

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot',required=True)
    ap.add_argument('--cmdline-file',required=True)
    ap.add_argument('--signing-registry')
    ap.add_argument('--evidence')
    a=ap.parse_args();work=Path(a.snapshot);p,rc,_=snapshot(work)
    evidence=json.loads(Path(a.evidence).read_text()) if a.evidence else {}
    registry=json.loads(Path(a.signing_registry).read_text()) if a.signing_registry else {}
    audit=json.loads((work/'result.json').read_text())
    # Evidence must refer to the exact audited partition hashes.
    bound=evidence.get('images')==audit.get('images') and bool(audit.get('images'))
    known=set(POLICY['forbidden_platform_sha256'])
    certified=signing_allowed(audit.get('signers',{}),registry,known)
    answer=evaluate(p,rc,Path(a.cmdline_file).read_text(),certified,evidence.get('checks',{}) if bound else {})
    print(json.dumps(answer,indent=2));raise SystemExit(0 if answer['release_allowed'] else 2)
