package com.roc.rgsp.lid;

public final class LidProfileTest {
    private static int checks;
    private static void check(boolean expected, String model, String lid,
            String device, String profile, boolean readable) {
        checks++;
        boolean actual = LidProfile.supported(model, lid, device, profile, readable);
        if (actual != expected) throw new AssertionError("model="+model+" lid="+lid
                +" device="+device+" profile="+profile+" readable="+readable);
    }
    public static void main(String[] args) {
        for (String lid : new String[] {"", "0", "1", "true", "2", " 1"})
            check(false, "rg35xxh", lid, "rgsp", "rg34xxsp", true);
        for (String model : new String[] {"rg34xxsp", "rgsp"}) {
            check(true, model, "1", "rgsp", "rg34xxsp", true);
            for (String lid : new String[] {"", "0", "true", "2", " 1"})
                check(false, model, lid, "rgsp", "rg34xxsp", true);
            check(false, model, "1", "other", "rg34xxsp", true);
            check(false, model, "1", "rgsp", "other", true);
            check(false, model, "1", "rgsp", "rg34xxsp", false);
        }
        check(true, "", "", "rgsp", "rg34xxsp", true);
        check(false, "", "", "other", "rg34xxsp", true);
        check(false, "", "", "rgsp", "other", true);
        check(false, "", "", "rgsp", "rg34xxsp", false);
        for (String model : new String[] {"", "unknown", "rg35xxsp", "RG34XXSP", "rg34xx"})
            check(false, model, "1", "rgsp", "rg34xxsp", true);
        check(false, "unknown", "", "rgsp", "rg34xxsp", true);
        System.out.println("LID_MODEL_PROFILE_PASS checks="+checks);
    }
}
