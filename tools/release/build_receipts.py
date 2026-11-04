"""Select current successful build receipts; never silently fall back to old audits."""
import json,re
from pathlib import Path

def numbered(directory, prefix):
 paths=[p for p in Path(directory).glob(prefix+'*.json') if re.fullmatch(re.escape(prefix)+r'\d+\.json',p.name)]
 return sorted(paths,key=lambda p:int(re.search(r'(\d+)\.json$',p.name)[1]))

def current_build(directory):
 paths=numbered(directory,'images-result-v')
 if not paths:raise ValueError('No image build receipt')
 path=paths[-1];built=json.loads(path.read_text())
 if not built.get('passed'):raise ValueError('Latest build failed; refuse older successful output')
 return path,built

def current_audit(directory):
 build,built=current_build(directory)
 audits=numbered(directory,'round2-audit-v')
 if not audits:raise ValueError('No partition audit receipt')
 audit=json.loads(audits[-1].read_text())
 if not audit.get('passed') or audit.get('build_receipt')!=build.name or audit.get('images')!=built.get('images'):
  raise ValueError('Latest audit does not accept the latest successful build')
 work=Path(audit['work']);snapshot=json.loads((work/'result.json').read_text())
 if not snapshot.get('passed') or snapshot.get('images')!=built['images']:
  raise ValueError('Audit work snapshot is inconsistent with build receipt')
 return build,built,work
