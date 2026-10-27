import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.UiAutomation;
import android.graphics.Rect;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.SystemClock;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.io.FileOutputStream;
import java.io.File;
import java.nio.file.Files;
import java.lang.reflect.Constructor;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

/** Passive hierarchy read: no input injection, accessibility clicks, or idle wait. */
public final class Dump {
    static int remaining;
    static String text(CharSequence s) { return s == null ? "" : s.toString(); }
    static JSONObject node(AccessibilityNodeInfo n) throws Exception {
        JSONObject j = new JSONObject();
        if (n == null || --remaining < 0) return j;
        if(!n.refresh()) return j;
        Rect r = new Rect(); n.getBoundsInScreen(r);
        j.put("id", text(n.getViewIdResourceName()));
        j.put("class", text(n.getClassName()));
        j.put("package", text(n.getPackageName()));
        j.put("text", n.isPassword() ? "[REDACTED]" : text(n.getText()));
        j.put("desc", n.isPassword() ? "[REDACTED]" : text(n.getContentDescription()));
        j.put("bounds", new JSONArray(new int[]{r.left,r.top,r.right,r.bottom}));
        j.put("enabled",n.isEnabled()); j.put("visible",n.isVisibleToUser());
        j.put("focusable",n.isFocusable()); j.put("focused",n.isFocused());
        j.put("accessibilityFocused",n.isAccessibilityFocused());
        j.put("clickable",n.isClickable()); j.put("longClickable",n.isLongClickable());
        j.put("scrollable",n.isScrollable()); j.put("editable",n.isEditable());
        j.put("checkable",n.isCheckable()); j.put("checked",n.isChecked());
        j.put("selected",n.isSelected()); j.put("actions",n.getActions());
        AccessibilityNodeInfo.CollectionItemInfo item=n.getCollectionItemInfo();
        if(item!=null) {
            JSONObject value=new JSONObject();
            value.put("row",item.getRowIndex()); value.put("column",item.getColumnIndex());
            j.put("collection",value);
        }
        AccessibilityNodeInfo.RangeInfo range=n.getRangeInfo();
        if(range!=null) {
            JSONObject value=new JSONObject(); value.put("min",range.getMin());
            value.put("max",range.getMax()); value.put("current",range.getCurrent());
            j.put("range",value);
        }
        JSONArray children = new JSONArray();
        // License HTML can expose tens of thousands of document nodes. It is
        // external read-only content, not a Settings control tree. Preserve the
        // WebView and all native siblings (toolbar/buttons), but do not block
        // every subsequent observation by walking this document's entire DOM.
        boolean licenseDocument = "android.webkit.WebView".equals(text(n.getClassName()))
                && ("com.android.htmlviewer".equals(text(n.getPackageName()))
                    || "com.android.webview".equals(text(n.getPackageName())));
        if (licenseDocument) j.put("childrenOmitted", "EXTERNAL_LICENSE_DOCUMENT_DOM");
        else for (int i=0;i<n.getChildCount() && remaining>0;i++) {
            AccessibilityNodeInfo child=n.getChild(i);
            if(child!=null) { children.put(node(child)); child.recycle(); }
        }
        j.put("children",children);
        return j;
    }
    static String snapshot(UiAutomation ui) throws Exception {
        JSONObject result=new JSONObject(); result.put("elapsed",SystemClock.elapsedRealtime());
        JSONArray windows=new JSONArray();
        List<AccessibilityWindowInfo> list=ui.getWindows();
        remaining=10000;
        for(AccessibilityWindowInfo w:list) {
            JSONObject item=new JSONObject();
            item.put("id",w.getId());
            item.put("type",w.getType()); item.put("focused",w.isFocused());
            item.put("active",w.isActive()); item.put("title",text(w.getTitle()));
            AccessibilityNodeInfo root=w.getRoot();
            if(root!=null) {root.refresh();item.put("root",node(root));root.recycle();}
            windows.put(item); w.recycle();
        }
        result.put("windows",windows);
        return result.toString();
    }
    public static void main(String[] args) throws Exception {
        HandlerThread thread = new HandlerThread("RGSPPassiveDump"); thread.start();
        Class<?> connectionType=Class.forName("android.app.IUiAutomationConnection");
        Object connection=Class.forName("android.app.UiAutomationConnection").getConstructor().newInstance();
        Constructor<?> ctor=UiAutomation.class.getConstructor(Looper.class,connectionType);
        UiAutomation ui=(UiAutomation)ctor.newInstance(thread.getLooper(),connection);
        try {
            // FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES: keep the actual navigation helper active.
            UiAutomation.class.getMethod("connect",int.class).invoke(ui,1);
            AccessibilityServiceInfo info=ui.getServiceInfo();
            info.flags |= AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                | AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
            ui.setServiceInfo(info);
            SystemClock.sleep(150);
            if(args.length==2 && args[0].equals("--daemon")) {
                File directory=new File(args[1]);
                if(!directory.isDirectory()) throw new IllegalArgumentException("Missing private output directory");
                File request=new File(directory,"request");
                File response=new File(directory,"response");
                new File(directory,"ready").createNewFile();
                long deadline=SystemClock.elapsedRealtime()+7200000L;
                int snapshots=0;
                System.out.println("PASSIVE_START pid="+android.os.Process.myPid()
                        +" max_heap="+Runtime.getRuntime().maxMemory());
                // A bounded observer lifetime releases the automation client's
                // native caches on this 1 GiB device during long menu audits.
                while(snapshots<64 && !new File(directory,"stop").exists() && SystemClock.elapsedRealtime()<deadline) {
                    if(request.exists()) {
                        String token=new String(Files.readAllBytes(request.toPath()),"UTF-8").trim();
                        request.delete();
                        if(!token.matches("[a-f0-9]{16}")) throw new IllegalArgumentException("Bad request token");
                        JSONObject envelope=new JSONObject();
                        envelope.put("token",token); envelope.put("snapshot",new JSONObject(snapshot(ui)));
                        File temp=new File(directory,"response.tmp");
                        Files.write(temp.toPath(),envelope.toString().getBytes("UTF-8"));
                        // Announce retirement before publishing the final reply;
                        // the next client waits for disconnect instead of racing it.
                        if(snapshots==63) new File(directory,"ready").delete();
                        if(!temp.renameTo(response)) throw new IllegalStateException("Response rename failed");
                        snapshots++;
                        if(snapshots%8==0) Runtime.getRuntime().gc();
                        if(snapshots%16==0) System.out.println("PASSIVE_SNAPSHOTS="+snapshots
                                +" used_heap="+(Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory()));
                    } else SystemClock.sleep(25);
                }
                new File(directory,"ready").delete();
                System.out.println("PASSIVE_BOUNDED_EXIT snapshots="+snapshots);
            } else {
                try(FileOutputStream out=new FileOutputStream(args[0])) {
                    out.write(snapshot(ui).getBytes("UTF-8"));
                }
                System.out.println("PASSIVE_DUMP_OK");
            }
        } finally {
            UiAutomation.class.getMethod("disconnect").invoke(ui);
            thread.quitSafely();
        }
    }
}
