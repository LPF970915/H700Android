package com.roc.rgsp.lid;

/** Boot selector identity gates only Hall control, not other input consumers. */
final class LidProfile {
    private LidProfile() { }

    static boolean supported(String model, String clamshell, String device,
            String inputProfile, boolean sensorReadable) {
        if (!sensorReadable || !"rgsp".equals(device)
                || !"rg34xxsp".equals(inputProfile)) return false;
        // Existing cards without a manual-selector identity retain their gate.
        if ("".equals(model) && "".equals(clamshell)) return true;
        // Never monitor an unused Hall input on a known flat handheld.
        if ("rg35xxh".equals(model)) return false;
        // Unknown, incomplete or inconsistent explicit identities fail closed.
        return ("rg34xxsp".equals(model) || "rgsp".equals(model))
                && "1".equals(clamshell);
    }
}
