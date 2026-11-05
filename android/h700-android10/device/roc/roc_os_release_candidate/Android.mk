LOCAL_PATH := $(call my-dir)
ifeq ($(TARGET_PRODUCT),roc_os_release_candidate)
# This parent Makefile owns discovery of the existing launcher child too.
roc_candidate_modules_path := $(LOCAL_PATH)
include $(roc_candidate_modules_path)/Launcher/Android.mk
# The retained Source64 parent gates these Make modules on its own product name.
# Import the identical guarded sources for this independent user product.
roc_candidate_source64_path := device/roc/roc_os_source64
GRALLOC_API_VERSION := 1.x
include $(roc_candidate_source64_path)/gralloc-variant/Android.mk
include $(roc_candidate_source64_path)/Wifi/Android.mk
endif
