package com.roc.rgsp.lid;

/** The user's boot-selected identity owns Hall policy; RAM is not identity. */
final class LidProfile {
    private LidProfile() { }

    static boolean supported(String model, String clamshell, String device,
            String inputProfile, boolean sensorReadable) {
        if (!sensorReadable) return false;
        // Compatibility for old cards that have no manual model selection.
        if ("".equals(model) && "".equals(clamshell)) {
            return "rgsp".equals(device) && "rg34xxsp".equals(inputProfile);
        }
        // Explicit identities do not inherit the old 34SP stick-driver gate.
        return "1".equals(clamshell) && ("rg34xxsp".equals(model)
                || "rgsp".equals(model) || "rg35xxsp".equals(model));
    }
}
