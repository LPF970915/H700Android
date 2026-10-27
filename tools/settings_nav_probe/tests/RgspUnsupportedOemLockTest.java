package com.android.server.oemlock;

/** Host regression: unsupported hardware must never grant an unlock request. */
public final class RgspUnsupportedOemLockTest {
    public static void main(String[] args) {
        RgspUnsupportedOemLock lock=new RgspUnsupportedOemLock();
        if(lock.isOemUnlockAllowedByCarrier() || lock.isOemUnlockAllowedByDevice())
            throw new AssertionError("Unsupported unlock was reported as allowed");
        boolean carrierRejected=false,deviceRejected=false;
        try { lock.setOemUnlockAllowedByCarrier(true,new byte[]{1}); }
        catch(UnsupportedOperationException expected) { carrierRejected=true; }
        try { lock.setOemUnlockAllowedByDevice(true); }
        catch(UnsupportedOperationException expected) { deviceRejected=true; }
        if(!carrierRejected || !deviceRejected) throw new AssertionError("Enable must fail");
        lock.setOemUnlockAllowedByCarrier(false,null);
        lock.setOemUnlockAllowedByDevice(false);
        if(lock.isOemUnlockAllowedByCarrier() || lock.isOemUnlockAllowedByDevice())
            throw new AssertionError("Rejected requests mutated lock state");
        System.out.println("PASS: unsupported carrier/device reads, enable rejection and disable idempotence");
    }
}
