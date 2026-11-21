"""Generate the Test20 menu, shell guard and preview writer from one model grouping."""

import json
import subprocess

from shared_trials import ASSETS, replace, source_of
from models import MODEL_METADATA

GROUPS = (
    ('rg35xxh', 'rg35xxplus', 'rg35xx_2025', 'rg28xx', 'rg35xxpro', 'rg35xxsp'),
    ('rg40xxv', 'rg40xxh'),
    ('rg34xxsp', 'rgsp'),
    ('rg34xx',),
    ('rgcubexx',),
)
REPS = tuple(group[0] for group in GROUPS)
GROUP_OF = {model: i for i, group in enumerate(GROUPS) for model in group}
assert set(GROUP_OF) == set(MODEL_METADATA) and sum(map(len, GROUPS)) == len(GROUP_OF)


def native_source():
    src = source_of('selector_rescue.c')
    src = replace(src, '*initial=DEFAULT_MODEL_ID', '*initial="rg35xxh"')
    reps = ', '.join(map(json.dumps, REPS))
    conditions = []
    for i, group in enumerate(GROUPS):
        conditions.append('    if (' + ' || '.join(f'!strcmp(id, "{m}")' for m in group) + f') return {i};')
    start = src.index('/* Three user-requested')
    end = src.index('static void fail', start)
    src = src[:start] + f'static const char *preview_cycle[] = {{{reps}}};\n\n' + src[end:]
    start = src.index('static unsigned preview_target')
    end = src.index('    unsigned target=', start)
    src = src[:start] + '''static unsigned panel_group(unsigned model) {
    const char *id = models[model].id;
''' + '\n'.join(conditions) + '''
    fprintf(stderr, "No panel group for %s\\n", id);
    exit(2);
}

static uint32_t panel_mask(unsigned initial) {
    unsigned group = panel_group(initial);
    uint32_t members = 0;
    for (unsigned i = 0; i < MODEL_COUNT; ++i) {
        if (panel_group(i) == group) members |= 1u << i;
    }
    return members;
}

static unsigned preview_target(unsigned active_model, bool next) {
    unsigned current = panel_group(active_model);
''' + src[end:]
    src = replace(src, '        state->model = (state->model + MODEL_COUNT + (event == LEFT ? -1 : 1)) % MODEL_COUNT;', '''
        unsigned candidate = state->model;
        for (unsigned i = 0; i < MODEL_COUNT; ++i) {
            candidate = (candidate + MODEL_COUNT + (event == LEFT ? -1 : 1)) % MODEL_COUNT;
            if (available_mask & (1u << candidate)) {
                state->model = candidate;
                break;
            }
        }''')
    src = replace(src, '    text(s,ox+48,oy+76,"←",true);text(s,ox+558,oy+76,"→",true);',
                  '''    if (available_mask & (available_mask - 1)) {
        text(s,ox+48,oy+76,"←",true);
        text(s,ox+558,oy+76,"→",true);
    }''')
    return replace(src, '    if(blind&&!geometry)', '''    unsigned initialized = find_model(initial);
    available_mask &= panel_mask(initialized);
    if (!(available_mask & (1u << initialized))) return 2;
    if(blind&&!geometry)''')


def hook_source():
    src = source_of('selector_init_rescue.sh')
    start = src.index('    # Resolve adjacency')
    end = src.index('    if [ "$CHOSEN" != "$TRIAL_NEXT"', start)
    src = src[:start] + src[end:]
    declarations = ['case "$MODEL" in']
    for i, group in enumerate(GROUPS):
        declarations.extend([
            '    ' + '|'.join(group) + ')',
            '        MENU_MODELS=' + ','.join(group),
            '        TRIAL_NEXT=' + REPS[(i + 1) % len(REPS)],
            '        TRIAL_PREV=' + REPS[i - 1] + ';;',
        ])
    declarations.extend(["    *) stop 'unknown panel group'; exit 1;;", 'esac'])
    src = replace(src, 'ROTATION=0', '\n'.join(declarations) + '\nROTATION=0')
    all_ids = 'rg34xx,rg34xxsp,rgsp,rgcubexx,rg35xxplus,rg35xx_2025,rg28xx,rg35xxh,rg40xxh,rg40xxv,rg35xxsp,rg35xxpro'
    src = replace(src, '--available-models ' + all_ids, '--available-models "$MENU_MODELS"')
    # Recover inside the hook. Its Test14 caller can continue Android on an error exit.
    guard = '''case ",$MENU_MODELS," in
    *,"$CHOSEN",*) ;;
    *) note "selection outside active panel: $CHOSEN"; retry_preview; continue;;
esac
RESTART=0
if [ "$MODEL" != "$CHOSEN" ]; then
    RESTART=1
else
    case "$CHOSEN" in rg40xxv|rg34xx) RESTART=1;; esac
fi
'''
    src = replace(src, 'fi\nif [ "$SAVE" = 1 ]; then\n    /grow/', 'fi\n' + guard + 'if [ "$SAVE" = 1 ]; then\n    /grow/')
    src = replace(src, 'elif [ "$CHOSEN" != "$MODEL" ]; then', 'elif [ "$RESTART" = 1 ]; then')
    return replace(src, 'if [ "$CHOSEN" = "$MODEL" ]; then', 'if [ "$RESTART" = 0 ]; then')


def build(work):
    files = {}
    old = '!strcmp(s,"rg35xxh")||!strcmp(s,"rg34xxsp")||!strcmp(s,"rgcubexx")'
    state = replace(source_of('boot_state_preview.c'), old, ' || '.join(f'!strcmp(s,"{m}")' for m in REPS))
    for name, src in [('selector', native_source()), ('state', state.replace('three-panel', 'menu-panel'))]:
        path = work / (name + '.c')
        path.write_text(src)
        output = work / name
        subprocess.run(['/usr/bin/aarch64-linux-gnu-gcc', '-static', '-std=c11', '-O2', '-Wall',
                        '-Wextra', '-Werror', '-Wno-misleading-indentation', '-fstack-protector-strong',
                        '-D_FORTIFY_SOURCE=2', '-I', ASSETS, path, '-o', output], check=True)
        files['grow/roc-boot-' + name] = output.read_bytes()
    hook = work / 'selector-init.sh'
    hook.write_text(hook_source())
    files['grow/roc-selector-init.sh'] = hook.read_bytes()
    return files
