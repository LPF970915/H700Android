package com.roc.rgsp.romsprobe;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.DocumentsContract;

public final class GrantActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state == null) {
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
            picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            picker.putExtra(DocumentsContract.EXTRA_INITIAL_URI,
                    DocumentsContract.buildDocumentUri("com.android.externalstorage.documents",
                            getIntent().getStringExtra("uuid") + ":"));
            startActivityForResult(picker, 1);
        }
    }

    @Override public void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == 1 && result == RESULT_OK && data != null) {
            getContentResolver().takePersistableUriPermission(data.getData(),
                    data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION
                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION));
            getSharedPreferences("probe", MODE_PRIVATE).edit()
                    .putString("tree", data.getData().toString()).commit();
        }
        finish();
    }
}
