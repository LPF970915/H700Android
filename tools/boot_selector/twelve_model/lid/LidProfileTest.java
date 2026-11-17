package com.roc.rgsp.lid;

public final class LidProfileTest {
    private static int checks;
    private static void check(boolean expected, String model, String lid,
            String device, String profile, boolean readable) {
        checks++;
        if (LidProfile.supported(model, lid, device, profile, readable) != expected)
            throw new AssertionError("model="+model+" lid="+lid+" device="+device
                    +" profile="+profile+" readable="+readable);
    }
    public static void main(String[] args) {
        String[] models = {"rg34xx", "rg34xxsp", "rgsp", "rgcubexx",
            "rg35xxplus", "rg35xx_2025", "rg28xx", "rg35xxh", "rg40xxh",
            "rg40xxv", "rg35xxsp", "rg35xxpro"};
        for (String model : models) {
            boolean folding = model.equals("rg34xxsp") || model.equals("rgsp")
                    || model.equals("rg35xxsp");
            for (String lid : new String[] {"", "0", "1", "true", "2", " 1"}) {
                for (String profile : new String[] {"rg34xxsp", model, ""}) {
                    check(folding && lid.equals("1"), model, lid, "rgsp", profile, true);
                    check(folding && lid.equals("1"), model, lid, "h700", profile, true);
                    check(false, model, lid, "rgsp", profile, false);
                }
            }
        }
        check(true, "", "", "rgsp", "rg34xxsp", true);
        check(false, "", "", "h700", "rg34xxsp", true);
        check(false, "", "", "rgsp", "", true);
        check(false, "", "", "rgsp", "rg34xxsp", false);
        for (String model : new String[] {"", "unknown", "RG34XXSP", "rg35xxsp "})
            check(false, model, "1", "rgsp", "rg34xxsp", true);
        System.out.println("LID_MODEL_PROFILE_PASS checks="+checks);
    }
}
