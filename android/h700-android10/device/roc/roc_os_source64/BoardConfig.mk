# Independent full-source build; keep the existing board products unchanged.
include device/roc/rgsp64proto/BoardConfig.mk

# The vendor wireless selector reads this file directly rather than its includes.
BOARD_WIFI_VENDOR := realtek
BOARD_USR_WIFI := RTL8821CS

DEVICE_MANIFEST_FILE := device/roc/roc_os_source64/manifest.xml
TARGET_RECOVERY_FSTAB := device/roc/roc_os_source64/configs/fstab.sun50iw9p1
BOARD_SEPOLICY_DIRS += device/roc/roc_os_source64/sepolicy
