package com.roc.rgsp.rotation;

/** Parse only the default display; an external screen must not change this tile. */
public final class RotationState {
    public static String primary(String dump) {
        String marker = "Display: mDisplayId=0";
        int start = dump.indexOf(marker);
        if (start < 0) return "";
        int end = dump.indexOf("Display: mDisplayId=", start + marker.length());
        return dump.substring(start, end < 0 ? dump.length() : end);
    }
    public static boolean fixed(String dump) {
        return primary(dump).contains("mFixedToUserRotation=true");
    }
    public static boolean applied(String dump) {
        return fixed(dump) && primary(dump).matches("(?s).*mUserRotation=ROTATION_0(?:\\s|$).*");
    }
    public static boolean hasTile(String specs, String shortName, String fullName) {
        if (specs == null) return false;
        for (String spec : specs.split(",")) {
            if (spec.trim().equals("custom(" + shortName + ")")
                    || spec.trim().equals("custom(" + fullName + ")")) return true;
        }
        return false;
    }
}
