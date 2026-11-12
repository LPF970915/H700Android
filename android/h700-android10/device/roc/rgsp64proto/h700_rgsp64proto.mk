# Must precede generic_no_telephony -> core_minimal to select dual Zygote.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
include device/roc/rgsp/h700_rgsp.mk

# Include, rather than inherit, the base product so its GPU entry is replaceable.
PRODUCT_COPY_FILES := $(filter-out %:vendor/lib/egl/libGLES_mali.so,$(PRODUCT_COPY_FILES))
PRODUCT_COPY_FILES += \
    device/roc/rgsp/configs/audio_mixer_paths.xml:vendor/etc/audio_mixer_paths.xml \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib/libGLES_mali.so:vendor/lib/egl/libGLES_mali.so \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so:vendor/lib64/egl/libGLES_mali.so

PRODUCT_NAME := h700_rgsp64proto
PRODUCT_DEVICE := rgsp64proto
PRODUCT_MODEL := RG34XXSP H700 Dual ABI Prototype
PRODUCT_PACKAGES += h700_window_probe H700AbiProbe64
PRODUCT_PACKAGES += gralloc.h700proto
GLOBAL_REMOVED_PACKAGES += gralloc.cupid
PRODUCT_PROPERTY_OVERRIDES += ro.hardware.gralloc=h700proto

# The build directory is new, but the physical device remains the same RGSP
# family. Existing input/power/navigation helpers explicitly guard this name.
PRODUCT_SYSTEM_DEFAULT_PROPERTIES += \
    ro.product.device=rgsp \
    ro.h700.prototype=rg34xxsp-dualabi-20261030 \
    persist.vendor.rgsp.input_profile=rg34xxsp
