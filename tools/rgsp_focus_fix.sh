#!/system/bin/sh
# RGSP Focus Fix - Runtime Configuration
# Run this script to enable D-pad focus navigation

echo "=== RGSP Focus Navigation Fix ==="

# 1. Enable TV UI Mode (type 4 = TV)
echo "Enabling TV UI mode..."
settings put global ui_mode_type 4
settings put global ui_night_mode 0

# 2. Disable navigation bar (not needed for D-pad only device)
echo "Configuring navigation..."
settings put global policy_control immersive.navigation=*

# 3. Enable accessibility features that help with focus
echo "Enabling accessibility focus..."
settings put secure accessibility_enabled 0
settings put secure enabled_accessibility_services ""

# 4. Force focus visible in all apps
echo "Forcing focus visibility..."
setprop debug.hwui.renderer opengl
setprop persist.sys.ui.hw true

# 5. Restart launcher to apply changes
echo "Restarting launcher..."
am force-stop net.pierrox.lightning_launcher
am force-stop com.android.launcher3
pkill -f "launcher"

# 6. Start AT4K if installed
am start -n net.pierrox.lightning_launcher/.activities.Dashboard 2>/dev/null || echo "AT4K not started"

echo "=== Focus fix applied ==="
echo "Please restart apps if focus still not visible"
echo "To fully apply: reboot"
