# This round validates the retained BSP sources, not the packaged GSI runtime.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
include device/roc/rgsp/h700_rgsp.mk

PRODUCT_NAME := roc_os_source64
PRODUCT_DEVICE := roc_os_source64
PRODUCT_MODEL := ROC OS
PRODUCT_PACKAGES := $(filter-out RGSPNavigation vold services wifi-service preinstall,$(PRODUCT_PACKAGES))
PRODUCT_PACKAGES += gralloc.rocsource ROCNavigation vold.rocsource services.rocsource wifi-service.rocsource \
    android.hardware.light@2.0-service.rocsource \
    roc-grow-userdata-gpt e2fsck_static roc-resize2fs-static
GLOBAL_REMOVED_PACKAGES += gralloc.cupid RGSPNavigation vold services wifi-service preinstall
# Pin the resolved list: filtering before inherit-product expansion can re-add services.
PRODUCT_SYSTEM_SERVER_JARS := services.rocsource ethernet-service wifi-service.rocsource com.android.location.provider
PRODUCT_PROPERTY_OVERRIDES += ro.hardware.gralloc=rocsource
PRODUCT_SYSTEM_DEFAULT_PROPERTIES += \
    ro.product.device=rgsp \
    persist.vendor.rgsp.input_profile=rg34xxsp \
    ro.roc.source64.round=2 \
    ro.roc.storage.layout=unified-v1

# This product has no third-party installer or TF1 ROMS handoff.
roc_removed_destinations := \
    system/etc/init/h700-preinstall.rc system/bin/h700-preinstall.sh \
    system/etc/init/preinstall.rc system/bin/preinstall \
    system/etc/init/rgsp-firstboot.rc system/bin/rgsp-firstboot.sh \
    system/etc/init/rgsp-navigation-defaults.rc system/bin/rgsp-navigation-defaults.sh \
    system/etc/init/rgsp-roms-handoff.rc system/bin/rgsp-roms-handoff.sh \
    system/etc/init/h700-usb-configfs.rc vendor/etc/fstab.sun50iw9p1 \
    fstab.sun50iw9p1
# Prepend replacements before inherit-product expansion. Vendor placeholders in
# inherited entries are resolved later; filtering literal vendor paths is not enough.
roc_source64_copy_files := \
    device/roc/roc_os_source64/configs/roc-source64-startup.rc:system/etc/init/roc-source64-startup.rc \
    device/roc/roc_os_source64/configs/audio_mixer_paths.xml:vendor/etc/audio_mixer_paths.xml \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm/lib/libGLES_mali.so:vendor/lib/egl/libGLES_mali.so \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so:vendor/lib64/egl/libGLES_mali.so \
    device/roc/roc_os_source64/Wifi/roc-wifi-events.rc:system/etc/init/roc-wifi-events.rc \
    device/roc/roc_os_source64/configs/fstab.sun50iw9p1:vendor/etc/fstab.sun50iw9p1 \
    device/roc/roc_os_source64/configs/h700-usb-configfs.rc:system/etc/init/h700-usb-configfs.rc \
    device/roc/roc_os_source64/configs/roc-os-branding.rc:system/etc/init/roc-os-branding.rc \
    device/roc/roc_os_source64/configs/roc-os-branding.sh:system/bin/roc-os-branding.sh \
    device/roc/roc_os_source64/configs/roc-factory.rc:system/etc/init/roc-factory.rc \
    device/roc/roc_os_source64/configs/roc-factory.sh:system/bin/roc-factory.sh
PRODUCT_COPY_FILES := $(roc_source64_copy_files) $(filter-out $(foreach d,$(roc_removed_destinations),%:$(d)),$(PRODUCT_COPY_FILES))
