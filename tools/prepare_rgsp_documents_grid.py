"""Keep file captions visible below compact thumbnails on the small RGSP screen."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/apps/DocumentsUI/src/com/android/documentsui/GridItemThumbnail.java'
BEFORE='1a39e4db279de125e9c2de3dc05a66cb5a5ca8c18d7cf23d3fa24809cfad8058'
OLD='''        super.onMeasure(widthMeasureSpec, widthMeasureSpec);'''
NEW='''        android.content.res.Configuration configuration = getResources().getConfiguration();
        if ("rgsp".equals(android.os.Build.DEVICE) && getId() == R.id.icon_thumb
                && configuration.orientation == android.content.res.Configuration.ORIENTATION_LANDSCAPE
                && configuration.screenHeightDp < 420 && MeasureSpec.getSize(widthMeasureSpec) > 0) {
            // Reserve the toolbar/filter/header and the file's nameplate. A
            // full square thumbnail can put even the first filename offscreen.
            int availableDp = Math.max(32, Math.min(96, configuration.screenHeightDp - 224));
            int height = Math.min(MeasureSpec.getSize(widthMeasureSpec),
                    Math.round(availableDp * getResources().getDisplayMetrics().density));
            super.onMeasure(widthMeasureSpec, MeasureSpec.makeMeasureSpec(height, MeasureSpec.EXACTLY));
            return;
        }
        super.onMeasure(widthMeasureSpec, widthMeasureSpec);'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();target=a.source/REL;text=target.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE:
        raise SystemExit('Unrecognized GridItemThumbnail edits; no files changed')
    if base.count(OLD)!=1:raise SystemExit('Ambiguous grid measure anchor')
    patched=base.replace(OLD,NEW,1);target.write_text(patched)
    (a.source/'out/rgsp-documents-grid-inputs.json').write_text(json.dumps(
        {'path':REL,'before':BEFORE,'after':hashlib.sha256(patched.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_COMPACT_GRID_CAPTIONS_PREPARED')


if __name__=='__main__':main()
