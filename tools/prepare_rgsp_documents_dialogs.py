"""Route RGSP file-name forms through one native TV dialog; preserve operation code."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SHARED='packages/apps/DocumentsUI/src/com/android/documentsui/base/Shared.java'
SHARED_BEFORE='4944b729d45707cb4f41f3f8fc2adc145577f4de75e022634ba4b77c0ca1b25b'
SHARED_RETIRED='de57efd2cfc691c3d096d5ea8eca1ae98303d92012b8febbacc23237cf8cd451'
ORIGINAL_METHOD='''    public static void ensureKeyboardPresent(Context context, AlertDialog dialog) {
        if (!isHardwareKeyboardAvailable(context)) {
            dialog.getWindow().setSoftInputMode(
                    WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE);
        }
    }
'''
RENAME='packages/apps/DocumentsUI/src/com/android/documentsui/dirlist/RenameDocumentFragment.java'
CREATE='packages/apps/DocumentsUI/src/com/android/documentsui/CreateDirectoryFragment.java'
RENAME_START='''        Context context = getActivity();'''
RENAME_PATCH=RENAME_START+'''
        if (com.android.documentsui.base.RgspFileNameDialog.applies(context)) {
            com.android.documentsui.base.RgspFileNameDialog input =
                    com.android.documentsui.base.RgspFileNameDialog.create(context,
                            R.string.menu_rename, R.string.input_hint_rename, name -> {
                                renameDocuments(name); return false;
                            });
            mEditText = input.editor;
            mRenameInputWrapper = null;
            mDialog = input.dialog;
            return input.dialog;
        }'''
ERROR_OLD='''            mRenameInputWrapper.setError(getContext().getString(R.string.name_conflict));'''
ERROR_NEW='''            if (mRenameInputWrapper != null) {
                mRenameInputWrapper.setError(getContext().getString(R.string.name_conflict));
            } else {
                mEditText.setError(getContext().getString(R.string.name_conflict));
            }'''
CREATE_START='''        final Context context = getActivity();'''
CREATE_PATCH=CREATE_START+'''
        if (com.android.documentsui.base.RgspFileNameDialog.applies(context)) {
            com.android.documentsui.base.RgspFileNameDialog input =
                    com.android.documentsui.base.RgspFileNameDialog.create(context,
                            R.string.menu_create_dir, R.string.input_hint_new_folder, name -> {
                                createDirectory(name); return true;
                            });
            return input.dialog;
        }'''


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();changes=[];proof={}
    shared=a.source/SHARED;text=shared.read_text();digest=sha(text.encode())
    if digest==SHARED_RETIRED:
        start=text.index('    public static void ensureKeyboardPresent(')
        end=text.index('\n    /**\n     * Returns true if "Documents" root should be shown.',start)
        base=text[:start]+ORIGINAL_METHOD+text[end:]
    else:base=text
    if sha(base.encode())!=SHARED_BEFORE:raise SystemExit('Unrecognized DocumentsUI Shared edits; no files changed')
    changes.append((shared,base.encode()));proof[SHARED]=SHARED_BEFORE
    for rel,before,edits in [
        (RENAME,'4bbf9e236494ab6d5a7a9e067e8aa5d589c8b5b5019e6d60d2728d243c60e382',[(RENAME_START,RENAME_PATCH),(ERROR_OLD,ERROR_NEW)]),
        (CREATE,'e49c86eff7e4e8e4cb4e1c217a8fccc411c0bf5cf501bf234f3d8bffe1927ed0',[(CREATE_START,CREATE_PATCH)])]:
        target=a.source/rel;text=target.read_text();base=text
        for old,new in reversed(edits):base=base.replace(new,old,1)
        if sha(base.encode())!=before:raise SystemExit('Unrecognized file-name fragment edits: '+rel)
        patched=base
        for old,new in edits:
            if patched.count(old)!=1:raise SystemExit('Ambiguous dialog patch anchor: '+rel)
            patched=patched.replace(old,new,1)
        changes.append((target,patched.encode()));proof[rel]=sha(patched.encode())
    helper=ROOT/'android/h700-android10/device/roc/rgsp/documents/RgspFileNameDialog.java'
    dest=a.source/'packages/apps/DocumentsUI/src/com/android/documentsui/base/RgspFileNameDialog.java'
    content=helper.read_bytes().replace(b'\r\n',b'\n')
    stage=a.source/'out/rgsp-documents-dialog-inputs.json'
    previous=json.loads(stage.read_text()) if stage.exists() else {}
    if dest.exists() and dest.read_bytes()!=content and previous.get('helper')!=sha(dest.read_bytes()):
        raise SystemExit('Unrecognized existing native file-name dialog helper')
    changes.append((dest,content));proof['helper']=sha(content)
    for target,content in changes:
        if not target.exists() or target.read_bytes()!=content:target.write_bytes(content)
    stage.write_text(json.dumps(proof,indent=2)+'\n')
    print('RGSP_SHARED_NATIVE_FILE_NAME_DIALOGS_PREPARED')


if __name__=='__main__':main()
