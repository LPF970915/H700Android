LOCAL_PATH := $(call my-dir)
ifeq ($(TARGET_PRODUCT),roc_os_source64)
roc_source64_path := $(LOCAL_PATH)
GRALLOC_API_VERSION := 1.x
include $(roc_source64_path)/gralloc-variant/Android.mk
include $(roc_source64_path)/Wifi/Android.mk
endif
