"""Produce an evidence inventory; a completed scan is not automatically a pass."""
import csv
import json
from pathlib import Path
from audit import OUT, descendants, signature

def main():
    pages={}
    sources=list(OUT.glob('exploration-??????????.json'))
    initial=OUT/'exploration-network-initial.json'
    if initial.exists(): sources.append(initial)
    for source in sorted(sources,key=lambda p:p.stat().st_mtime):
        try: data=json.loads(source.read_text(encoding='utf-8'))
        except json.JSONDecodeError: continue
        for page in data['pages']:
            pages['/'.join(page['path'])]=dict(page,source=source.name)
    overview=[]; controls=[]; review=[]
    for path,page in sorted(pages.items()):
        missing=[]; unknown=[]
        for sig,control in page['controls'].items():
            controls.append({'path':path,'label':control['label'],'action':control['action'],
                'evidence':control['evidence']})
            if control['action']!='unclassified': continue
            raw=json.loads((OUT/control['evidence']).read_text(encoding='utf-8'))
            found=next((n for w in raw['windows'] for n in descendants(w.get('root',{})) if signature(n)==sig),{})
            if found.get('clickable'): unknown.append(control['label'])
        reached={c['label'] for c in page['controls'].values()}
        for candidate in page['visible_controls'].values():
            if not candidate['enabled'] or not candidate['clickable']: continue
            if candidate['label'] in reached or candidate['label']=='向上导航': continue
            if 'RecyclerView' in candidate['class'] or 'ListView' in candidate['class']: continue
            missing.append(candidate['label'])
        overview.append({'path':path,'status':page['status'],'focused_controls':len(page['controls']),
            'branches':len(page['branches']),'unclassified_clickable':' | '.join(unknown),
            'branches_without_transition':' | '.join(b['label'] for b in page['branches'] if b.get('result')=='NO_TRANSITION'),
            'candidate_focus_gaps':' | '.join(dict.fromkeys(missing)),
            'screenshot':page['entry'].get('screenshot',''),'source':page['source']})
        if unknown or missing or overview[-1]['branches_without_transition'] or page['status'] not in ('VERTICAL_SCAN_DONE','BIDIRECTIONAL_SCAN_DONE','DUPLICATE_TEMPLATE'):
            review.append(overview[-1])
    for name,rows in [('pages',overview),('controls',controls),('review',review)]:
        if not rows: continue
        with (OUT/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (OUT/'coverage.json').write_text(json.dumps({'pages':overview,'review':review},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Pages:',len(overview),'Controls:',len(controls),'Review:',len(review))
    for r in review:
        print(r['path'],r['status'],'UNKNOWN='+r['unclassified_clickable'],'GAPS='+r['candidate_focus_gaps'])

if __name__=='__main__': main()
