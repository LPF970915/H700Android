LOCAL_PATH := $(call my-dir)
ifeq ($(TARGET_PRODUCT),h700_rgsp64proto)
# Generated only from the retained BSP source plus two logging-format fixes.
# The original upstream Gralloc tree remains byte-for-byte unchanged.
GRALLOC_API_VERSION := 1.x
include $(LOCAL_PATH)/gralloc-variant/Android.mk
endif
