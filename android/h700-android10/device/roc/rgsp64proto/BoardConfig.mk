# Experimental product only. The shipping ARM32 board is inherited, not edited.
include device/roc/rgsp/BoardConfig.mk

# The vendor product parser scans this file with sed rather than evaluating
# nested includes. Keep these two selectors visible to wireless_config.mk.
BOARD_WIFI_VENDOR := realtek
BOARD_USR_WIFI := RTL8821CS

TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_VARIANT := cortex-a53
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_ABI2 :=
TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv7-a-neon
TARGET_2ND_CPU_VARIANT := cortex-a7
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_SUPPORTS_32_BIT_APPS := true
TARGET_SUPPORTS_64_BIT_APPS := true
