package com.roc.rgsp.rotation;

public final class RotationStateTest {
    private static int count;
    private static void check(boolean expected, boolean actual) {
        count++;
        if (expected != actual) throw new AssertionError("rotation state mismatch");
    }
    public static void main(String[] args) {
        String on = "Display: mDisplayId=0\nmFixedToUserRotation=true\nmUserRotation=ROTATION_0\n";
        String off = "Display: mDisplayId=0\nmFixedToUserRotation=false\nmUserRotation=ROTATION_270\n";
        String external = "Display: mDisplayId=2\nmFixedToUserRotation=true\nmUserRotation=ROTATION_0\n";
        check(true, RotationState.applied(on));
        check(false, RotationState.applied(off));
        check(false, RotationState.applied(external));
        check(false, RotationState.applied(external + off));
        check(true, RotationState.applied(external + on));
        check(false, RotationState.applied(off + external));
        check(false, RotationState.applied(on.replace("ROTATION_0", "ROTATION_090")));
        check(false, RotationState.applied(on.replace("ROTATION_0", "ROTATION_270")));
        check(false, RotationState.applied(""));
        check(true, RotationState.fixed(on));
        check(false, RotationState.fixed(off));
        String shortName = "com.roc.rgsp.rotation/.LandscapeTile";
        String fullName = "com.roc.rgsp.rotation/com.roc.rgsp.rotation.LandscapeTile";
        check(true, RotationState.hasTile("wifi,custom(" + shortName + "),bt", shortName, fullName));
        check(true, RotationState.hasTile("custom(" + fullName + ")", shortName, fullName));
        check(false, RotationState.hasTile(null, shortName, fullName));
        check(false, RotationState.hasTile("custom(" + shortName + "Extra)", shortName, fullName));
        check(false, RotationState.hasTile("wifi,rotation,bt", shortName, fullName));
        System.out.println("H700_ROTATION_STATE_PASS assertions=" + count);
    }
}
