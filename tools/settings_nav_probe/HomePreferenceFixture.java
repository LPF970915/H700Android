/** Test setup only: temporarily clear this board's AT4K HOME preference. No input injection. */
public final class HomePreferenceFixture {
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !"--clear-at4k-home".equals(args[0])) {
            throw new IllegalArgumentException("Explicit --clear-at4k-home required");
        }
        Class<?> props = Class.forName("android.os.SystemProperties");
        String serial = (String) props.getMethod("get", String.class).invoke(null, "ro.serialno");
        if (!"5c001089d750c872012".equals(serial)) throw new SecurityException("Wrong device");
        Object pm = Class.forName("android.app.AppGlobals").getMethod("getPackageManager").invoke(null);
        Class.forName("android.content.pm.IPackageManager")
            .getMethod("clearPackagePreferredActivities", String.class).invoke(pm, "com.overdevs.at4k");
        System.out.println("AT4K_HOME_PREFERENCE_CLEARED_FOR_TEST");
    }
}
