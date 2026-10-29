"""Small ActivityRecord compatibility changes; leaves orientation requests intact."""
import re

HELPER = r'''.method private h700ForceLandscape()Z
    .registers 3
    const-string v0, "ro.product.device"
    invoke-static {v0}, Landroid/os/SystemProperties;->get(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    const-string v1, "rgsp"
    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :h700_not_forced
    invoke-virtual {p0}, Lcom/android/server/wm/ActivityRecord;->getDisplay()Lcom/android/server/wm/ActivityDisplay;
    move-result-object v0
    if-eqz v0, :h700_not_forced
    iget v1, v0, Lcom/android/server/wm/ActivityDisplay;->mDisplayId:I
    if-nez v1, :h700_not_forced
    iget-object v0, v0, Lcom/android/server/wm/ActivityDisplay;->mDisplayContent:Lcom/android/server/wm/DisplayContent;
    if-eqz v0, :h700_not_forced
    invoke-virtual {v0}, Lcom/android/server/wm/DisplayContent;->getDisplayRotation()Lcom/android/server/wm/DisplayRotation;
    move-result-object v0
    invoke-virtual {v0}, Lcom/android/server/wm/DisplayRotation;->isFixedToUserRotation()Z
    move-result v0
    return v0
    :h700_not_forced
    const/4 v0, 0x0
    return v0
.end method
'''

INJECTIONS = {
    'getRequestedConfigurationOrientation()I': '''
    invoke-direct/range {p0 .. p0}, Lcom/android/server/wm/ActivityRecord;->h700ForceLandscape()Z
    move-result v0
    if-eqz v0, :h700_orientation_original
    const/4 v0, 0x2
    return v0
    :h700_orientation_original
''',
    'shouldUseSizeCompatMode()Z': '''
    invoke-direct/range {p0 .. p0}, Lcom/android/server/wm/ActivityRecord;->h700ForceLandscape()Z
    move-result v0
    if-eqz v0, :h700_compat_original
    const/4 v0, 0x0
    return v0
    :h700_compat_original
''',
    'computeBounds(Landroid/graphics/Rect;Landroid/graphics/Rect;)V': '''
    invoke-direct/range {p0 .. p0}, Lcom/android/server/wm/ActivityRecord;->h700ForceLandscape()Z
    move-result v0
    if-eqz v0, :h700_bounds_original
    invoke-virtual/range {p1 .. p1}, Landroid/graphics/Rect;->setEmpty()V
    return-void
    :h700_bounds_original
''',
    'resolveOverrideConfiguration(Landroid/content/res/Configuration;)V': '''
    invoke-direct/range {p0 .. p0}, Lcom/android/server/wm/ActivityRecord;->h700ForceLandscape()Z
    move-result v0
    if-eqz v0, :h700_resolve_original
    const/4 v0, 0x0
    iput-object v0, p0, Lcom/android/server/wm/ActivityRecord;->mCompatDisplayInsets:Lcom/android/server/wm/ActivityRecord$CompatDisplayInsets;
    :h700_resolve_original
''',
}

def methods(text):
    return {m.group(1).split()[-1]: m.group(0)
            for m in re.finditer(r'^\.method ([^\n]+)\n.*?^\.end method', text, re.M | re.S)}

def patch(text):
    if 'h700ForceLandscape' in text:
        raise ValueError('Already patched ActivityRecord')
    original = methods(text)
    for signature, injected in INJECTIONS.items():
        if signature not in original:
            raise ValueError('Missing expected method: ' + signature)
        block = original[signature]
        found = re.search(r'(?m)^    \.(?:registers|locals) (\d+)\s*$', block)
        if not found or int(found.group(1)) < 1:
            raise ValueError('Unexpected register declaration')
        replacement = block[:found.end()] + '\n' + injected + block[found.end():]
        text = text.replace(block, replacement, 1)
    return text + '\n' + HELPER

def canonical(text):
    # Assembly can widen equivalent string/goto instructions as pool indices move.
    # DEX omits trailing default false static-field initializers when rebuilding.
    text = re.sub(r'(?m)^(\.field [^\n]*\bstatic\b[^\n]*:Z) = false$', r'\1', text)
    text = re.sub(r'const-string/jumbo\b', 'const-string', text)
    text = re.sub(r'goto/(?:16|32)\b', 'goto', text)
    names = re.findall(r'(?m)^\s*(:[A-Za-z_]+[0-9a-f]+)\s*$', text)
    mapping = {name: ':label_' + str(n) for n, name in enumerate(dict.fromkeys(names))}
    text = re.sub(r':[A-Za-z_]+[0-9a-f]+\b', lambda m: mapping.get(m[0], m[0]), text)
    return '\n'.join(s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#'))
