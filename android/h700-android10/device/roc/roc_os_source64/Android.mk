LOCAL_PATH := $(call my-dir)
ifeq ($(TARGET_PRODUCT),roc_os_source64)
GRALLOC_API_VERSION := 1.x
include $(LOCAL_PATH)/gralloc-variant/Android.mk
endif
