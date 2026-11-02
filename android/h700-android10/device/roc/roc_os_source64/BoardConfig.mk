# Independent full-source build; keep the existing board products unchanged.
include device/roc/rgsp64proto/BoardConfig.mk

# The vendor wireless selector reads this file directly rather than its includes.
BOARD_WIFI_VENDOR := realtek
BOARD_USR_WIFI := RTL8821CS
