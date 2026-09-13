LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := AT4K
LOCAL_SRC_FILES := AT4K.apk
LOCAL_CERTIFICATE := PRESIGNED
LOCAL_PRIVILEGED_MODULE := true
LOCAL_MODULE_CLASS := APPS
LOCAL_MODULE_TAGS := optional
LOCAL_MODULE_SUFFIX := $(COMMON_ANDROID_PACKAGE_SUFFIX)
LOCAL_DEX_PREOPT := false
# The checked-in APK is already page-aligned with stored JNI/dex entries.
# Legacy PRESIGNED repacking strips v2/v3 signatures, so copy it unchanged.
LOCAL_REPLACE_PREBUILT_APK_INSTALLED := $(LOCAL_PATH)/AT4K.apk
include $(BUILD_PREBUILT)
