package com.roc.rgsp.romsprobe;

import android.app.Instrumentation;
import android.content.Context;
import android.content.ContentResolver;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Process;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import java.io.File;
import java.io.FileOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.UUID;

public final class RomsProbe extends Instrumentation {
    private Bundle args;

    @Override public void onCreate(Bundle arguments) {
        args = arguments;
        start();
    }

    private static void require(boolean value, String message) {
        if (!value) throw new IllegalStateException(message);
    }

    private static String read(ContentResolver resolver, Uri uri) throws Exception {
        try (InputStream in = resolver.openInputStream(uri);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[128];
            int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            require(Process.myUid() >= 10000, "Probe must use an ordinary app UID");
            String uuid = args.getString("uuid");
            require(uuid != null && uuid.matches("[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}"), "UUID");
            StorageManager sm = getTargetContext().getSystemService(StorageManager.class);
            boolean found = false;
            for (StorageVolume vol : sm.getStorageVolumes()) {
                if (uuid.equalsIgnoreCase(vol.getUuid())) {
                    require(!vol.isPrimary(), "ROMS must not replace emulated primary storage");
                    require(Environment.MEDIA_MOUNTED.equals(vol.getState()), "Volume not mounted");
                    found = true;
                }
            }
            require(found, "ROMS not visible through the app StorageManager API");
            File root = new File("/storage/" + uuid);
            SharedPreferences state = getTargetContext().getSharedPreferences("probe", Context.MODE_PRIVATE);
            String granted = state.getString("tree", null);
            require(granted != null, "Select the ROMS directory in the system picker first");
            Uri tree = Uri.parse(granted);
            require((uuid + ":").equals(DocumentsContract.getTreeDocumentId(tree)), "Wrong tree grant");
            ContentResolver resolver = getTargetContext().getContentResolver();
            Uri parent = DocumentsContract.buildDocumentUriUsingTree(tree,
                    DocumentsContract.getTreeDocumentId(tree));
            String phase = args.getString("phase", "create");
            if ("create".equals(phase)) {
                require(!state.contains("directory"), "A persistence probe is already pending");
                Uri dir = DocumentsContract.createDocument(resolver, parent,
                        DocumentsContract.Document.MIME_TYPE_DIR,
                        "RGSP_STORAGE_PROBE_" + System.currentTimeMillis());
                require(dir != null, "Create shared directory failed");
                Uri file = DocumentsContract.createDocument(resolver, dir, "text/plain", "roundtrip.txt");
                require(file != null, "Create shared document failed");
                String nonce = UUID.randomUUID().toString();
                try (ParcelFileDescriptor fd = resolver.openFileDescriptor(file, "w");
                     FileOutputStream out = new FileOutputStream(fd.getFileDescriptor())) {
                    out.write(nonce.getBytes(StandardCharsets.UTF_8));
                    out.getFD().sync();
                }
                require(nonce.equals(read(resolver, file)), "Read-after-write mismatch");
                require(state.edit().putString("directory", dir.toString()).putString("nonce", nonce)
                        .putString("file", file.toString()).putString("uuid", uuid).commit(),
                        "Save probe receipt failed");
                boolean appDirectoryTested = false;
                for (File appDir : getTargetContext().getExternalFilesDirs(null)) {
                    if (appDir == null || !appDir.getPath().startsWith(root + "/")) continue;
                    File own = File.createTempFile("own-write-", ".txt", appDir);
                    Files.write(own.toPath(), nonce.getBytes(StandardCharsets.UTF_8));
                    require(nonce.equals(new String(Files.readAllBytes(own.toPath()),
                            StandardCharsets.UTF_8)), "App-owned directory mismatch");
                    require(own.delete(), "App-owned cleanup failed");
                    appDirectoryTested = true;
                }
                require(appDirectoryTested, "ROMS app-owned directory unavailable");
                result.putString("path", file.toString());
            } else if ("verify".equals(phase)) {
                require(uuid.equals(state.getString("uuid", "")), "Receipt belongs to another volume");
                Uri dir = Uri.parse(state.getString("directory", ""));
                require(DocumentsContract.getDocumentId(dir)
                        .matches(uuid + ":RGSP_STORAGE_PROBE_[0-9]+"), "Invalid saved directory");
                Uri file = Uri.parse(state.getString("file", ""));
                Uri renamed = null;
                String actual;
                try {
                    actual = read(resolver, file);
                } catch (java.io.FileNotFoundException | IllegalArgumentException missing) {
                    // A provider can commit rename and die before returning its result.
                    renamed = DocumentsContract.buildDocumentUriUsingTree(tree,
                            DocumentsContract.getDocumentId(dir) + "/renamed.txt");
                    actual = read(resolver, renamed);
                }
                require(actual.equals(state.getString("nonce", "")), "Persistence mismatch");
                if (renamed == null) {
                    renamed = DocumentsContract.renameDocument(resolver, file, "renamed.txt");
                }
                require(renamed != null, "Rename failed");
                require(DocumentsContract.deleteDocument(resolver, renamed), "Delete failed");
                require(DocumentsContract.deleteDocument(resolver, dir), "Directory cleanup failed");
                require(state.edit().remove("directory").remove("file").remove("nonce")
                        .remove("uuid").commit(), "Clear receipt failed");
            } else {
                throw new IllegalArgumentException("Unknown phase");
            }
            result.putInt("uid", Process.myUid());
            result.putLong("total_bytes", root.getTotalSpace());
            result.putLong("available_bytes", root.getUsableSpace());
            result.putString("stream", "ROMS_APP_" + phase.toUpperCase() + "_PASS\n");
            finish(-1, result);
        } catch (Exception error) {
            result.putString("stream", "ROMS_APP_FAIL: " + error + "\n");
            finish(0, result);
        }
    }
}
