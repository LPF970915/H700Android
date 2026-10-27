"""Expose semantic show-on-screen for RGSP file rows to reveal their full captions."""
import argparse
import hashlib
import json
from pathlib import Path
REL='packages/apps/DocumentsUI/src/com/android/documentsui/dirlist/AccessibilityEventRouter.java'
BEFORE='3083ede5aa5937e16b53a3aee0014e53d42b212b69f1cc7b93bca610eea57f5d'
EDITS=[
('                info.setSelected(host.isActivated());', '                info.setSelected(host.isActivated());\n                if ("rgsp".equals(android.os.Build.DEVICE)) {\n                    info.addAction(AccessibilityActionCompat.ACTION_SHOW_ON_SCREEN);\n                }'),
('                // We are only handling click events; route all other to default implementation', '                if ("rgsp".equals(android.os.Build.DEVICE)\n                        && action == AccessibilityActionCompat.ACTION_SHOW_ON_SCREEN.getId()) {\n                    return host.requestRectangleOnScreen(\n                            new android.graphics.Rect(0, 0, host.getWidth(), host.getHeight()), true);\n                }\n                // We are only handling click events; route all other to default implementation')]
BAR_REL='packages/apps/DocumentsUI/src/com/android/documentsui/NavigationViewManager.java'
BAR_BEFORE='c3651338a28cac8e82997016c01b23a432dce72e74fad43bcef638d8a89e6821'
BAR_OLD='''                (AppBarLayout.LayoutParams) mCollapsingBarLayout.getLayoutParams();
        if (shouldShowSearchBar()) {'''
BAR_NEW='''                (AppBarLayout.LayoutParams) mCollapsingBarLayout.getLayoutParams();
        if ("rgsp".equals(android.os.Build.DEVICE)) {
            // Keep filters and toolbar in the D-pad viewport. The file list
            // already reserves the app bar height as padding and scrolls alone.
            lp.setScrollFlags(0);
        } else if (shouldShowSearchBar()) {'''

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();target=a.source/REL;text=target.read_text();base=text
    for old,new in reversed(EDITS):base=base.replace(new,old,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE:raise SystemExit('Unrecognized accessibility router edits; no files changed')
    patched=base
    for old,new in EDITS:
        if patched.count(old)!=1:raise SystemExit('Ambiguous file visibility anchor')
        patched=patched.replace(old,new,1)
    bar=a.source/BAR_REL;bar_text=bar.read_text();bar_base=bar_text.replace(BAR_NEW,BAR_OLD,1)
    if hashlib.sha256(bar_base.encode()).hexdigest()!=BAR_BEFORE:
        raise SystemExit('Unrecognized navigation bar edits; no files changed')
    if bar_base.count(BAR_OLD)!=1:raise SystemExit('Ambiguous static app bar anchor')
    bar_patched=bar_base.replace(BAR_OLD,BAR_NEW,1)
    target.write_text(patched);bar.write_text(bar_patched)
    (a.source/'out/rgsp-documents-visible-inputs.json').write_text(json.dumps({'path':REL,'before':BEFORE,'after':hashlib.sha256(patched.encode()).hexdigest(),'bar_path':BAR_REL,'bar_before':BAR_BEFORE,'bar_after':hashlib.sha256(bar_patched.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_FILE_FOCUS_VISIBILITY_PREPARED')
if __name__=='__main__':main()
