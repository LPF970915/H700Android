"""Verify the product's absent encryption backend has no execution entry."""
import json
from audit import Audit, OUT, descendants
from followup import enter, top


def main():
    a=Audit();result={}
    try:
        enter(a,['安全','加密与凭据']);top(a)
        walk=a.walk('credentials-product-policy',70)
        labels={entry['label'] for entry in walk['visible_candidates'].values()}
        result={'labels':sorted(labels),'steps':len(walk['path'])}
        if any('加密手机' in value for value in labels):raise RuntimeError('Unconfigured encryption action is still offered')
        if not any('凭据' in value for value in labels):raise RuntimeError('Credential settings were hidden unexpectedly')
        result['status']='ENCRYPTION_ACTION_ABSENT_CREDENTIALS_REACHABLE'
        print(result['status'],flush=True)
    finally:
        a.close();(OUT/'encryption-menu-policy-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
