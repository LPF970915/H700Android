// SPDX-License-Identifier: Apache-2.0
package com.android.server.wifi;

import java.io.IOException;

/** Bounds retries of the still-buffered snapshot. Runs on the existing Wi-Fi handler. */
public final class RocStoreWriteRetry {
    public interface Writer { void write() throws IOException; }
    private int retries;
    public void newSnapshot() { retries = 0; }
    public int retries() { return retries; }
    public void write(Writer writer, Runnable requeue) throws IOException {
        try {
            writer.write();
            retries = 0;
        } catch (IOException failure) {
            if (retries < 3) {
                retries++;
                requeue.run();
            }
            throw failure;
        }
    }
}
