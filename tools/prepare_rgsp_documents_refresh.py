"""Expose native file refresh in the RGSP D-pad overflow menu."""
import argparse,hashlib,json
from pathlib import Path
REL='packages/apps/DocumentsUI/src/com/android/documentsui/files/FilesActivity.java'
BEFORE='09c9be36cce92036a4488a7fab0449450b76b62f1306101136fc1045dabceb3b'
OLD='    @Override\n    public boolean onOptionsItemSelected(MenuItem item) {\n        DirectoryFragment dir;'
NEW='    @Override\n    public boolean onCreateOptionsMenu(Menu menu) {\n        boolean result = super.onCreateOptionsMenu(menu);\n        if ("rgsp".equals(android.os.Build.DEVICE) && menu.findItem(R.id.rgsp_refresh) == null) {\n            // Pull-to-refresh must also be available to a D-pad-only device.\n            menu.add(Menu.NONE, R.id.rgsp_refresh, Menu.NONE, R.string.rgsp_refresh)\n                    .setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);\n        }\n        return result;\n    }\n\n    @Override\n    public boolean onOptionsItemSelected(MenuItem item) {\n        if ("rgsp".equals(android.os.Build.DEVICE) && item.getItemId() == R.id.rgsp_refresh) {\n            DirectoryFragment current = getDirectoryFragment();\n            if (current != null) current.onRefresh();\n            else mInjector.actions.loadDocumentsForCurrentStack();\n            return true;\n        }\n        DirectoryFragment dir;'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();target=a.source/REL;text=target.read_text();base=text.replace(NEW,OLD,1)
    if hashlib.sha256(base.encode()).hexdigest()!=BEFORE:raise SystemExit('Unrecognized FilesActivity edits; no files changed')
    if base.count(OLD)!=1:raise SystemExit('Ambiguous refresh menu anchor')
    patched=base.replace(OLD,NEW,1);target.write_text(patched)
    (a.source/'out/rgsp-documents-refresh-inputs.json').write_text(json.dumps({'path':REL,'before':BEFORE,'after':hashlib.sha256(patched.encode()).hexdigest()},indent=2)+'\n')
    print('RGSP_NATIVE_REFRESH_MENU_PREPARED')
if __name__=='__main__':main()
