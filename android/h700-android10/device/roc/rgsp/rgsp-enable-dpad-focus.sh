#!/system/bin/sh
# RGSP D-pad Focus Navigation Enabler
# This script enables TV UI mode and focus visibility for D-pad navigation

# Enable TV UI mode
settings put global ui_mode_type 4

# Force enable focus visibility
settings put system show_touches 0
settings put system pointer_location 0

# Enable accessibility focus for all apps
settings put secure accessibility_display_magnification_enabled 0

# Set default IME to LeanbackIME for better D-pad support
ime set com.google.android.leanbacklauncher.recommendations/.InputMethodService 2>/dev/null || true

echo "D-pad focus navigation enabled"
