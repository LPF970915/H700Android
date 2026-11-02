"""User-visible branding only; preserve hardware, ABI and release identities."""
import re

MODEL = 'ROC OS'
MODEL_KEYS = ('ro.product.model',) + tuple(
    'ro.product.' + scope + '.model'
    for scope in ('system', 'vendor', 'odm', 'product', 'system_ext'))


def brand_properties(content, *, system=False):
    values = {key: MODEL for key in MODEL_KEYS}
    if system:
        values['ro.build.display.id'] = 'ROC OS ARM64 Test'
    original = dict(re.findall(r'^([^#\s=]+)=(.*)$', content, re.M))
    for key, value in values.items():
        content = re.sub(r'^' + re.escape(key) + r'=.*(?:\n|$)', '', content, flags=re.M)
        content = content.rstrip('\n') + '\n' + key + '=' + value + '\n'
    after = dict(re.findall(r'^([^#\s=]+)=(.*)$', content, re.M))
    assert all(after[k] == v for k, v in original.items() if k not in values)
    assert all(after[k] == v for k, v in values.items())
    return content
