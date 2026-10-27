"""Resolve Settings preference titles to navigation/dialog metadata from local AOSP."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

A='{http://schemas.android.com/apk/res/android}'
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    items={}
    for resource_path in ('packages/apps/Settings/res','packages/inputmethods/LatinIME/java/res'):
        res=args.source/resource_path
        strings={}
        # Keep each application's string namespace separate.
        for locale in ('values','values-zh-rCN'):
            for base in [args.source/'frameworks/base/packages/SettingsLib/res',res]:
                for path in sorted((base/locale).glob('*.xml')):
                    try: tree=ET.parse(path)
                    except ET.ParseError: continue
                    for n in tree.getroot():
                        if n.tag=='string':
                            value=''.join(n.itertext()).strip()
                            if len(value)>1 and value[0]==value[-1]=='"': value=value[1:-1]
                            strings[n.get('name')]=value.replace('\\n','\n').replace("\\'", "'").replace('\\"','"')
        for path in sorted((res/'xml').glob('*.xml')):
            try: tree=ET.parse(path)
            except ET.ParseError: continue
            for n in tree.iter():
                title=n.get(A+'title','')
                if title.startswith('@string/'): title=strings.get(title[8:],title)
                if not title: continue
                intent=n.find('intent')
                record={'xml':resource_path+'/'+path.name,'type':n.tag,'key':n.get(A+'key',''),
                        'fragment':n.get(A+'fragment',''),
                        'intent':dict(intent.attrib) if intent is not None else None}
                items.setdefault(title,[]).append(record)
    args.output.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Resolved titles:',len(items))

if __name__=='__main__': main()
