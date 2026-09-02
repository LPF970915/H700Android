LOCAL_PATH := $(call my-dir)

$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_no_telephony.mk)
$(call inherit-product, build/target/product/go_defaults.mk)
$(call inherit-product-if-exists, device/softwinner/common/common.mk)
$(call inherit-product, device/roc/h700-common/device.mk)

PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/fstab.sun50iw9p1:$(TARGET_COPY_OUT_RAMDISK)/fstab.sun50iw9p1 \
    $(LOCAL_PATH)/fstab.sun50iw9p1:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.sun50iw9p1 \
    $(LOCAL_PATH)/init.rgsp.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/init.rgsp.rc \
    $(LOCAL_PATH)/ueventd.rgsp.rc:$(TARGET_COPY_OUT_VENDOR)/ueventd.rc

PRODUCT_SHIPPING_API_LEVEL := 29
PRODUCT_CHARACTERISTICS := nosdcard
PRODUCT_USE_DYNAMIC_PARTITIONS := false

PRODUCT_BRAND := ROC
PRODUCT_MANUFACTURER := ANBERNIC
PRODUCT_NAME := h700_rgsp
PRODUCT_DEVICE := rgsp
PRODUCT_BOARD := rgsp
PRODUCT_MODEL := RGSP H700

PRODUCT_SYSTEM_DEFAULT_PROPERTIES += \
    persist.sys.usb.config=adb \
    ro.adb.secure=0 \
    persist.sys.timezone=Asia/Shanghai \
    ro.radio.noril=yes
