include device/softwinner/common/BoardConfigCommon.mk

# RGSP is a fixed internal LCD handheld, not an HDMI/CVBS Homlet product.
# Keep the H616/Cupid board selector for the 4.9/ION ABI, but compile future
# display components through their non-Homlet path.
TARGET_PLATFORM := tablet
TARGET_BOARD_PLATFORM := cupid
TARGET_BOARD_CHIP := sun50iw9p1
# Keep the H616 selector for the Android 10 vendor build. H700 is the product
# identity and kernel/DTB target; the H616 selector chooses the compatible HALs.
TARGET_BOARD_IC := h616

$(call soong_config_add,vendor,board,$(TARGET_BOARD_PLATFORM))
$(call soong_config_add,vendor,platform,$(TARGET_PLATFORM))

TARGET_ARCH := arm
TARGET_ARCH_VARIANT := armv7-a-neon
TARGET_CPU_VARIANT := cortex-a7
TARGET_CPU_ABI := armeabi-v7a
TARGET_CPU_ABI2 := armeabi

TARGET_USES_64_BIT_BINDER := true
TARGET_SUPPORTS_32_BIT_APPS := true
TARGET_FLATTEN_APEX := true

USE_OPENGL_RENDERER := true
NUM_FRAMEBUFFER_SURFACE_BUFFERS := 3
TARGET_USES_HWC2 := true
TARGET_GPU_TYPE := mali-g31
TARGET_USES_DE30 := true
TARGET_USES_G2D := true
USE_IOMMU := true

MALLOC_SVELTE := true
BOARD_VNDK_VERSION := current

# Allwinner's global hardware/aw/widevine/Android.mk requires a valid source
# directory selector even when the product does not package any DRM modules.
BOARD_WIDEVINE_OEMCRYPTO_LEVEL := 3
BOARD_HAS_SECURE_OS := false

# The RGSP kernel and DTB remain external verified inputs during bring-up.
BOARD_INCLUDE_DTB_IN_BOOTIMG := true

include hardware/aw/gpu/product_config.mk
