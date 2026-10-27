/* Copyright (C) 2026 The Android Open Source Project
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 */
package com.android.server.oemlock;

/** Reports unsupported bootloader unlock without accessing an invented FRP partition. */
final class RgspUnsupportedOemLock extends OemLock {
    @Override String getLockName() { return "rgsp-unsupported"; }
    @Override boolean isOemUnlockAllowedByCarrier() { return false; }
    @Override boolean isOemUnlockAllowedByDevice() { return false; }
    @Override void setOemUnlockAllowedByCarrier(boolean allowed, byte[] signature) {
        rejectEnable(allowed);
    }
    @Override void setOemUnlockAllowedByDevice(boolean allowed) { rejectEnable(allowed); }
    private static void rejectEnable(boolean allowed) {
        if (allowed) {
            throw new UnsupportedOperationException("RGSP has no OEM unlock HAL or FRP backend");
        }
    }
}
