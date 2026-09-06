LOCAL_PATH := device/roc/rgsp

$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_no_telephony.mk)
$(call inherit-product, build/target/product/go_defaults.mk)
$(call inherit-product-if-exists, device/softwinner/common/common.mk)
$(call inherit-product, device/roc/h700-common/device.mk)

PRODUCT_COPY_FILES += \
    device/roc/rgsp/fstab.sun50iw9p1:$(TARGET_COPY_OUT_RAMDISK)/fstab.sun50iw9p1 \
    device/roc/rgsp/fstab.sun50iw9p1:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.sun50iw9p1 \
    device/roc/rgsp/init.rgsp.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/init.rgsp.rc \
    device/roc/rgsp/ueventd.rgsp.rc:$(TARGET_COPY_OUT_VENDOR)/ueventd.rc

PRODUCT_COPY_FILES += \
    device/roc/rgsp/rgsp-input-bringup.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/rgsp-input-bringup.rc \
    device/roc/rgsp/rgsp-input-prepare.sh:$(TARGET_COPY_OUT_VENDOR)/bin/rgsp-input-prepare.sh \
    device/roc/rgsp/rgsp-kmsg-start.sh:$(TARGET_COPY_OUT_VENDOR)/bin/rgsp-kmsg-start.sh

PRODUCT_PACKAGES += rgsp_kmsg_logger

# This product is RGSP-specific, not a shared H700 input profile.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/ANBERNIC-keys.kl:$(TARGET_COPY_OUT_SYSTEM)/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl \
    device/roc/rgsp/ANBERNIC-keys.kl:$(TARGET_COPY_OUT_SYSTEM)/usr/keylayout/Vendor_0001_Product_0001.kl \
    device/roc/rgsp/ANBERNIC-keys.kl:$(TARGET_COPY_OUT_SYSTEM)/usr/keylayout/ANBERNIC-keys.kl

# Default HIDL wrappers for the bring-up manifest. These do not provide the
# missing device Gatekeeper backend; secure-OS integration is still pending.
PRODUCT_PACKAGES += \
    android.hardware.gatekeeper@1.0-impl \
    android.hardware.gatekeeper@1.0-service \
    android.hardware.health@2.0-impl \
    android.hardware.health@2.0-service \
    android.hardware.keymaster@3.0-impl \
    android.hardware.keymaster@3.0-service

PRODUCT_SHIPPING_API_LEVEL := 29
PRODUCT_CHARACTERISTICS := nosdcard
PRODUCT_USE_DYNAMIC_PARTITIONS := false

# Temporary H700 kernel compatibility: no working VSYNC uevent producer.
# Requires tools/h616-hwc-rgsp-software-vsync.patch in the H616 source tree.
PRODUCT_PROPERTY_OVERRIDES += persist.vendor.hwc.software_vsync=true

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
    ro.product.platform=tablet \
    ro.radio.noril=yes
