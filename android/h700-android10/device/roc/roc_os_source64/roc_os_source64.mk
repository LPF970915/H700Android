# This round validates the retained BSP sources, not the packaged GSI runtime.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
include device/roc/rgsp/h700_rgsp.mk

# Use the previously tested dual-ABI Mali input with a private Gralloc module.
PRODUCT_COPY_FILES := $(filter-out %:vendor/lib/egl/libGLES_mali.so %:vendor/etc/audio_mixer_paths.xml,$(PRODUCT_COPY_FILES))
PRODUCT_COPY_FILES += \
    device/roc/rgsp/configs/audio_mixer_paths.xml:vendor/etc/audio_mixer_paths.xml \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib/libGLES_mali.so:vendor/lib/egl/libGLES_mali.so \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so:vendor/lib64/egl/libGLES_mali.so

PRODUCT_NAME := roc_os_source64
PRODUCT_DEVICE := roc_os_source64
PRODUCT_MODEL := ROC OS
PRODUCT_PACKAGES += gralloc.rocsource
GLOBAL_REMOVED_PACKAGES += gralloc.cupid
PRODUCT_PROPERTY_OVERRIDES += ro.hardware.gralloc=rocsource
PRODUCT_SYSTEM_DEFAULT_PROPERTIES += \
    ro.product.device=rgsp \
    persist.vendor.rgsp.input_profile=rg34xxsp \
    ro.roc.source64.round=1
