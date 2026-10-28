LOCAL_PATH := device/roc/rgsp

$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_no_telephony.mk)
$(call inherit-product, build/target/product/go_defaults.mk)
$(call inherit-product-if-exists, device/softwinner/common/common.mk)
$(call inherit-product, device/roc/h700-common/device.mk)
include device/softwinner/common/config/wireless/wireless_config.mk

# Allwinner's GPU product_config.mk does not match the mali-bifrost selector
# in this source release, so install the verified 32-bit G31 EGL blob here.
PRODUCT_COPY_FILES += \
    hardware/aw/gpu/mali-bifrost/mali-g31/arm/lib/libGLES_mali.so:$(TARGET_COPY_OUT_VENDOR)/lib/egl/libGLES_mali.so

PRODUCT_COPY_FILES += \
    device/roc/rgsp/fstab.sun50iw9p1:$(TARGET_COPY_OUT_RAMDISK)/fstab.sun50iw9p1 \
    device/roc/rgsp/fstab.sun50iw9p1:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.sun50iw9p1 \
    device/roc/rgsp/init.rgsp.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/init.rgsp.rc \
    device/roc/rgsp/ueventd.rgsp.rc:$(TARGET_COPY_OUT_VENDOR)/ueventd.rc

# The module and RTL Bluetooth firmware were extracted from this RGSP's
# original Linux image. They are hardware-specific and must not be replaced
# by the projector's RTL8822BS files.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/prebuilts/wifi/8821cs.ko:$(TARGET_COPY_OUT_VENDOR)/modules/8821cs.ko \
    device/roc/rgsp/prebuilts/wifi/rtl8821c_config:$(TARGET_COPY_OUT_VENDOR)/firmware/rtlbt/rtl8821c_config \
    device/roc/rgsp/prebuilts/wifi/rtl8821c_fw:$(TARGET_COPY_OUT_VENDOR)/firmware/rtlbt/rtl8821c_fw

PRODUCT_COPY_FILES += \
    device/roc/rgsp/rgsp-input-bringup.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/rgsp-input-bringup.rc \
    device/roc/rgsp/rgsp-input-prepare.sh:$(TARGET_COPY_OUT_VENDOR)/bin/rgsp-input-prepare.sh \
    device/roc/rgsp/rgsp-kmsg-start.sh:$(TARGET_COPY_OUT_VENDOR)/bin/rgsp-kmsg-start.sh

# Optional, per-device RG34XXSP axes; built against the pinned running BSP ABI.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/input/prebuilt/h700_stick_axes.ko:$(TARGET_COPY_OUT_VENDOR)/modules/h700_stick_axes.ko \
    device/roc/rgsp/input/rgsp-stick-axes.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/rgsp-stick-axes.rc \
    device/roc/rgsp/input/rgsp-stick-axes.sh:$(TARGET_COPY_OUT_VENDOR)/bin/rgsp-stick-axes.sh

PRODUCT_PACKAGES += rgsp_kmsg_logger RGSPLauncher AT4K RGSPNavigation

# Explicit guarded Wi-Fi debugging, started from UART only.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/rgsp-wifi-adb-session.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/rgsp-wifi-adb-session.sh

PRODUCT_COPY_FILES += \
    device/roc/rgsp/rgsp-roms-handoff.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/rgsp-roms-handoff.sh \
    device/roc/rgsp/rgsp-roms-handoff.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/rgsp-roms-handoff.rc

# Select AT4K before the first HOME intent, independently of late IME provisioning.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/configs/at4k-home.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/preferred-apps/at4k-home.xml

# Keep originals browsable; additional JPEGs in this directory join the next image.
PRODUCT_COPY_FILES += \
    $(foreach image,$(wildcard device/roc/rgsp/wallpapers/*.jpg),$(image):$(TARGET_COPY_OUT_SYSTEM)/media/wallpapers/$(notdir $(image))) \
    device/roc/rgsp/rgsp-wallpapers.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/rgsp-wallpapers.sh \
    device/roc/rgsp/rgsp-wallpapers.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/rgsp-wallpapers.rc

# Fetch the pinned AOSP source with tools/prepare_h700_leanback_ime.sh first.
# Keep LatinIME available for recovery and future touch-capable devices.
PRODUCT_PACKAGES += LeanbackIME
PRODUCT_PACKAGE_OVERLAYS += device/roc/rgsp/overlay

# Staged from local, hash-verified Fix67 inputs by prepare_rgsp_build_inputs.py.
# These generated files and the proprietary kernel module are not in Git.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/prebuilts/local/mali_kbase.ko:$(TARGET_COPY_OUT_SYSTEM)/lib/modules/mali_kbase.ko \
    device/roc/rgsp/prebuilts/local/rgsp_fix63_graphics.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/rgsp_fix63_graphics.rc \
    device/roc/rgsp/prebuilts/local/rgsp-graphics-diag.sh:$(TARGET_COPY_OUT_SYSTEM)/etc/rgsp-graphics-diag.sh \
    device/roc/rgsp/prebuilts/local/set_rgsp_home.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/set_rgsp_home.sh \
    device/roc/rgsp/rgsp-firstboot.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/rgsp-firstboot.sh \
    device/roc/rgsp/rgsp-firstboot.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/rgsp-firstboot.rc \
    device/roc/rgsp/rgsp-navigation-defaults.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/rgsp-navigation-defaults.sh \
    device/roc/rgsp/rgsp-navigation-defaults.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/rgsp-navigation-defaults.rc \
    device/roc/rgsp/rgsp-single-console.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/rgsp-single-console.rc \
    device/roc/rgsp/configs/leanback.sha256:$(TARGET_COPY_OUT_SYSTEM)/etc/rgsp/leanback.sha256 \
    device/roc/rgsp/configs/display-config.json:$(TARGET_COPY_OUT_VENDOR)/etc/dispconfigs/config.json \
    device/roc/rgsp/configs/h700-rgsp-lcd.json:$(TARGET_COPY_OUT_VENDOR)/etc/dispconfigs/h700-rgsp-lcd.json

# Keep a visible local file browser and the ordinary, permission-gated installer.
PRODUCT_PACKAGES += DocumentsUI PackageInstaller

# H700 exposes EHCI/OHCI host controllers. This also starts the framework USB service.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/configs/android.hardware.usb.host.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.usb.host.xml

# IOmxStore requires a catalog even with the separate Codec2 software APEX.
# Qualify software codecs first; do not advertise the donor's hardware codecs.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/configs/media_codecs.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs.xml \
    frameworks/av/media/libstagefright/data/media_codecs_google_audio.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs_google_audio.xml \
    frameworks/av/media/libstagefright/data/media_codecs_google_video.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs_google_video.xml

# This product is RGSP-specific, not a shared H700 input profile.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/ANBERNIC-keys.kl:$(TARGET_COPY_OUT_SYSTEM)/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl \
    device/roc/rgsp/ANBERNIC-keys.kl:$(TARGET_COPY_OUT_SYSTEM)/usr/keylayout/Vendor_0001_Product_0001.kl \
    device/roc/rgsp/ANBERNIC-keys.kl:$(TARGET_COPY_OUT_SYSTEM)/usr/keylayout/ANBERNIC-keys.kl

# Keep only HALs with a verified RGSP backend. Gatekeeperd has an in-process
# software fallback when no device GateKeeper service is declared.
PRODUCT_PACKAGES += \
    android.hardware.health@2.0-impl \
    android.hardware.health@2.0-service \
    android.hardware.keymaster@3.0-impl \
    android.hardware.keymaster@3.0-service

# The inherited Cupid HAL list unconditionally adds the HIDL Gatekeeper
# implementation, but RGSP has no matching secure backend. Keep gatekeeperd's
# in-process software fallback and remove only the unavailable provider.
PRODUCT_PACKAGES -= \
    android.hardware.gatekeeper@1.0-impl \
    android.hardware.gatekeeper@1.0-service \
    gatekeeper.cupid

GLOBAL_REMOVED_PACKAGES += \
    android.hardware.gatekeeper@1.0-impl \
    android.hardware.gatekeeper@1.0-service \
    gatekeeper.cupid

PRODUCT_SHIPPING_API_LEVEL := 29
PRODUCT_CHARACTERISTICS := nosdcard
PRODUCT_USE_DYNAMIC_PARTITIONS := false

# RGSP has no secure-OS Gatekeeper backend. gatekeeperd falls back to its
# built-in software implementation, while Android 10's FCM still marks the
# HIDL provider as mandatory at build time.
PRODUCT_ENFORCE_VINTF_MANIFEST_OVERRIDE := false

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
    debug.hwui.renderer=opengl \
    debug.hwui.use_buffer_age=false \
    debug.hwui.use_partial_updates=false \
    persist.display.policy=single \
    persist.disp.device_config=/vendor/etc/dispconfigs/h700-rgsp-lcd.json \
    ro.radio.noril=yes \
    persist.sys.ui.hw=true \
    ro.config.media_vol_steps=100 \
    config.disable_consumerir=true

# Framework default covers HOME and the inherited native lock wallpaper before
# the launcher's first resume; AT4K also synchronizes later custom-image changes.
PRODUCT_SYSTEM_DEFAULT_PROPERTIES += ro.config.wallpaper=/system/media/wallpapers/IMG_3111.jpg

# This handheld has a permanent D-pad and no touchscreen.
# Remove inherited donor touchscreen features so native toolbars accept D-pad focus.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/configs/android.hardware.touchscreen.unavailable.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.touchscreen.unavailable.xml

# Initialize the kernel's ConfigFS gadget and preserve normal adbd/function policy.
PRODUCT_COPY_FILES += \
    device/roc/rgsp/h700-usb-configfs.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/h700-usb-configfs.rc \
    device/roc/rgsp/h700-network-validation-defaults.rc:$(TARGET_COPY_OUT_SYSTEM)/etc/init/h700-network-validation-defaults.rc \
    device/roc/rgsp/h700-network-validation-defaults.sh:$(TARGET_COPY_OUT_SYSTEM)/bin/h700-network-validation-defaults.sh

