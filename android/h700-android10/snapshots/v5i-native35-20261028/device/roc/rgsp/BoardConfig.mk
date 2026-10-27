include device/roc/h700-common/BoardConfigCommon.mk

# The donor defines TARGET_SYSTEM_PROP, so Make ignores the implicit board file.
# Append this product's defaults explicitly while preserving the donor files.
TARGET_SYSTEM_PROP += device/roc/rgsp/system.prop

# Product-level Wi-Fi service configuration for the RGSP RTL8821CS module.
# The path is intentionally a complete .ko path: this Android 10 HAL branch
# passes non-COMMON vendor paths directly to finit_module().
BOARD_WIFI_VENDOR := realtek
BOARD_USR_WIFI := RTL8821CS
WIFI_DRIVER_MODULE_NAME := 8821cs
WIFI_DRIVER_MODULE_PATH := /vendor/modules/8821cs.ko
# The BSP reload path waits for wlan0 and p2p0, not the stock Linux wlan1.
WIFI_DRIVER_MODULE_ARG := if2name=p2p0

# The RGSP kernel and DTB are verified external inputs. Android's build graph
# must not require a source-tree kernel to produce system/vendor/ramdisk.
TARGET_NO_KERNEL := true

TARGET_BOOTLOADER_BOARD_NAME := rgsp
TARGET_NO_BOOTLOADER := true

BOARD_USES_VENDORIMAGE := true
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4
TARGET_COPY_OUT_VENDOR := vendor
BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEMIMAGE_PARTITION_SIZE := 8589934592
BOARD_VENDORIMAGE_PARTITION_SIZE := 2147483648

TARGET_RECOVERY_FSTAB := device/roc/rgsp/fstab.sun50iw9p1
DEVICE_MANIFEST_FILE += device/roc/rgsp/manifest.xml
BOARD_ROOT_EXTRA_FOLDERS += rgsp-persist
BOARD_SEPOLICY_DIRS += device/roc/rgsp/sepolicy
