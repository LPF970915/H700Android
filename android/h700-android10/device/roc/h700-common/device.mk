LOCAL_PATH := $(call my-dir)

PRODUCT_PACKAGES += \
    android.hardware.graphics.allocator@2.0-impl \
    android.hardware.graphics.allocator@2.0-service \
    android.hardware.graphics.mapper@2.0-impl-2.1 \
    android.hardware.graphics.composer@2.2-impl \
    android.hardware.graphics.composer@2.2-service \
    gralloc.cupid \
    hwcomposer.cupid \
    android.hardware.audio@2.0-service \
    android.hardware.audio@5.0-impl \
    android.hardware.audio.effect@5.0-impl \
    audio.primary.cupid \
    android.hardware.memtrack@1.0-impl \
    android.hardware.memtrack@1.0-service \
    memtrack.cupid \
    libion

# Use the Android 10 H616 policy generation while the RGSP mixer paths are
# narrowed to its internal audiocodec, card 0/device 0.
PRODUCT_COPY_FILES += \
    device/softwinner/cupid-common/configs/audio_policy_configuration.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_policy_configuration.xml \
    device/softwinner/cupid-common/configs/audio_platform_info.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_platform_info.xml \
    device/softwinner/cupid-common/configs/audio_effects.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_effects.xml \
    device/softwinner/cupid-common/configs/audio_policy_volumes_drc.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_policy_volumes_drc.xml \
    device/softwinner/cupid-common/configs/usb_audio_policy_configuration.xml:$(TARGET_COPY_OUT_VENDOR)/etc/usb_audio_policy_configuration.xml \
    device/softwinner/cupid-perf1/configs/audio_mixer_paths.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_mixer_paths.xml

PRODUCT_SYSTEM_DEFAULT_PROPERTIES += \
    ro.config.low_ram=true \
    ro.lmk.use_psi=true \
    ro.config.per_app_memcg=false \
    ro.kernel.android.checkjni=0

PRODUCT_PROPERTY_OVERRIDES += \
    ro.opengles.version=196610 \
    ro.sf.lcd_density=213 \
    vendor.audio.output.active=AUDIO_CODEC \
    vendor.audio.input.active=AUDIO_CODEC
