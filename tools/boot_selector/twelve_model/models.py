"""Explicit twelve-model routing; no RAM, serial or resolution identity gate.

Panel indexes identify complete electrical programs, not geometry groups.  The
2025 model currently shares the retained Plus reference as an explicit candidate
assumption.  The 28XX requires a separate native portrait/rotated output route.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/boot_selector'))
from reference_model import MODEL_CATALOG

PROPERTIES = ('roc_panel_profile', 'lcd_x', 'lcd_y', 'lcd_dclk_freq', 'lcd_hbp',
              'lcd_ht', 'lcd_hspw', 'lcd_vbp', 'lcd_vt', 'lcd_vspw',
              'lcd_hv_clk_phase', 'lcd_hv_sync_polarity', 'lcd_frm')
VALUES = (
    (0,720,480,26,46,820,2,20,536,5,1,3,1),
    (1,640,480,24,46,770,20,15,520,4,2,3,1),
    (2,720,480,26,46,820,2,20,536,5,1,3,1),
    (3,720,720,48,46,1060,2,20,755,5,0,0,1),
    (4,640,480,24,46,770,20,15,520,4,2,3,1),
    (5,480,640,24,56,586,6,26,686,6,0,0,0),
    (6,640,480,24,46,770,20,15,522,4,2,3,1),
    (7,640,480,24,46,770,20,15,522,4,2,3,1),
    (8,640,480,48,48,1414,8,48,566,4,2,3,1),
    (9,640,480,24,46,770,20,14,528,4,2,3,1),
)
MODEL_PROFILE = {
    'rg34xx':2, 'rg34xxsp':0, 'rgsp':0, 'rgcubexx':3,
    'rg35xxplus':4, 'rg35xx_2025':4, 'rg28xx':5, 'rg35xxh':1,
    'rg40xxh':6, 'rg40xxv':7, 'rg35xxsp':8, 'rg35xxpro':9,
}
ALL_MODEL_IDS = tuple(model.model_id for model in MODEL_CATALOG)
assert set(MODEL_PROFILE) == set(ALL_MODEL_IDS)
TIMINGS = {index: dict(zip(PROPERTIES[1:], values[1:]))
           for index, values in enumerate(VALUES)}
MODEL_METADATA = {
    model.model_id: dict(model.to_mapping(), panel_profile=MODEL_PROFILE[model.model_id],
        native_size=list(VALUES[MODEL_PROFILE[model.model_id]][1:3]),
        display_rotation=90 if model.model_id == 'rg28xx' else 0,
        reference_assumption=('uses Plus reference; 2025-specific hardware unverified'
                              if model.model_id == 'rg35xx_2025' else None),
        ram_gate=False, physical_accepted=False)
    for model in MODEL_CATALOG
}


def assembly_tables():
    lines = ['/* Generated from twelve_model/models.py; profile indexes are electrical. */',
             '.p2align 2', '.Lvalues:']
    lines += ['    .word ' + ','.join(map(str, values)) for values in VALUES]
    lines += ['.Lmodels:']
    for model in ALL_MODEL_IDS:
        lines += ['    .asciz "' + model + '"', '    .byte ' + str(MODEL_PROFILE[model])]
    lines += ['    .byte 0', '']
    return '\n'.join(lines)
