"""Prototype-only SystemUI power-menu coverage; leave the release v8 tree intact."""


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Navigation source anchor changed: ' + old[:70])
    return text.replace(old, new)


def patch(text):
    text = replace_once(text,
        'if ("com.android.systemui".equals(pkg)) return shadeRoot(root) ? "shade" : "inactive";',
        'if ("com.android.systemui".equals(pkg)) return powerRoot(root) ? "power" : shadeRoot(root) ? "shade" : "inactive";')
    text = replace_once(text, '|| "shade".equals(mode);', '|| "shade".equals(mode) || "power".equals(mode);')
    text = replace_once(text,
        'if (!((PowerManager) getSystemService(POWER_SERVICE)).isInteractive()\n'
        '                || ((KeyguardManager) getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked()) {',
        'if (!((PowerManager) getSystemService(POWER_SERVICE)).isInteractive()) {')
    text = replace_once(text, 'AccessibilityNodeInfo shade = null;',
        'AccessibilityNodeInfo shade = null;\n        AccessibilityNodeInfo power = null;')
    text = replace_once(text, 'if (shadeRoot(root)) {',
        'if (powerRoot(root)) {\n'
        '                        if (power != null) power.recycle();\n'
        '                        power = AccessibilityNodeInfo.obtain(root);\n'
        '                    }\n                    if (shadeRoot(root)) {')
    text = replace_once(text, 'if (shade != null) { if (result != null) result.recycle(); return shade; }',
        'if (power != null) {\n'
        '            if (result != null) result.recycle();\n'
        '            if (shade != null) shade.recycle();\n'
        '            return power;\n        }\n'
        '        if (((KeyguardManager) getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked()) {\n'
        '            if (result != null) result.recycle();\n'
        '            if (shade != null) shade.recycle();\n'
        '            return null;\n        }\n'
        '        if (shade != null) { if (result != null) result.recycle(); return shade; }')
    text = replace_once(text, 'private void collectItems(AccessibilityNodeInfo root, List<AccessibilityNodeInfo> items) {',
        'private void collectItems(AccessibilityNodeInfo root, List<AccessibilityNodeInfo> items) {\n'
        '        if ("power".equals(mode)) { collectPower(root, items); return; }')
    text = replace_once(text, 'int next = "shade".equals(mode) && (key == Direction.LEFT || key == Direction.RIGHT)',
        'int next = "power".equals(mode) ? Math.max(0, Math.min(items.size()-1, index +\n'
        '                    (key==Direction.UP || key==Direction.LEFT ? -1 : 1)))\n'
        '                    : "shade".equals(mode) && (key == Direction.LEFT || key == Direction.RIGHT)')
    text = replace_once(text, 'int key = event.getKeyCode();\n        if (key == KeyEvent.KEYCODE_BUTTON_B',
        'int key = event.getKeyCode();\n'
        '        if (SystemClock.uptimeMillis() >= releaseUntil && (key == KeyEvent.KEYCODE_BUTTON_B\n'
        '                || key == KeyEvent.KEYCODE_BACK || key == KeyEvent.KEYCODE_ESCAPE)) {\n'
        '            if (event.getAction()==KeyEvent.ACTION_DOWN && !powerBack) powerBack=powerDialogVisible();\n'
        '            if (powerBack) {\n'
        '                if (event.getAction()==KeyEvent.ACTION_UP) {\n'
        '                    powerBack=false; if (!event.isCanceled()) back();\n'
        '                }\n                return true;\n            }\n        }\n'
        '        if (key == KeyEvent.KEYCODE_BUTTON_B')
    methods = '''
    private boolean powerBack;

    private boolean powerRoot(AccessibilityNodeInfo root) {
        if (root == null || !"com.android.systemui".equals(String.valueOf(root.getPackageName()))) return false;
        List<AccessibilityNodeInfo> nodes=root.findAccessibilityNodeInfosByViewId("com.android.systemui:id/global_actions_view");
        boolean visible=false;
        for (AccessibilityNodeInfo node:nodes) { visible |= node.isVisibleToUser(); node.recycle(); }
        return visible;
    }

    private boolean powerDialogVisible() {
        boolean visible=false;
        for (AccessibilityWindowInfo window:getWindows()) {
            if (window.getType()==AccessibilityWindowInfo.TYPE_SYSTEM) {
                AccessibilityNodeInfo root=window.getRoot();
                visible |= powerRoot(root);
                if (root!=null) root.recycle();
            }
            window.recycle();
        }
        return visible;
    }

    private void collectPower(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> items) {
        if (!node.refresh() || !node.isVisibleToUser() || !node.isEnabled()) return;
        if (node.isClickable()) {
            List<AccessibilityNodeInfo> labels=node.findAccessibilityNodeInfosByViewId("android:id/message");
            boolean single=labels.size()==1;
            recycle(labels);
            if (single) { items.add(AccessibilityNodeInfo.obtain(node)); return; }
        }
        for (int i=0;i<node.getChildCount();i++) {
            AccessibilityNodeInfo child=node.getChild(i);
            if (child!=null) { collectPower(child,items); child.recycle(); }
        }
    }
'''
    return replace_once(text, '    private String scope(AccessibilityNodeInfo root) {',
                        methods + '\n    private String scope(AccessibilityNodeInfo root) {')
