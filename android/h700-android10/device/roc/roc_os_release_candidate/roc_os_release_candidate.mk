# Isolated user candidate; never substitute the live eng product/output.
$(call inherit-product, device/roc/roc_os_source64/roc_os_source64.mk)
include $(dir $(lastword $(MAKEFILE_LIST)))release_properties.mk
# Replace inherited root startup helpers only in this independent user product.
roc_user_retired := system/etc/rgsp/leanback.sha256 system/etc/init/h700-network-validation-defaults.rc system/bin/h700-network-validation-defaults.sh \
    system/etc/init/rgsp-wallpapers.rc system/bin/rgsp-wallpapers.sh \
    vendor/etc/init/rgsp-stick-axes.rc vendor/bin/rgsp-stick-axes.sh \
    vendor/etc/init/rgsp-input-bringup.rc vendor/bin/rgsp-input-prepare.sh vendor/bin/rgsp-kmsg-start.sh \
    system/bin/rgsp-wifi-adb-session.sh
roc_user_retired_sources := device/roc/rgsp/configs/leanback.sha256 device/roc/rgsp/h700-network-validation-defaults.rc device/roc/rgsp/h700-network-validation-defaults.sh device/roc/rgsp/rgsp-wallpapers.rc device/roc/rgsp/rgsp-wallpapers.sh device/roc/rgsp/input/rgsp-stick-axes.rc device/roc/rgsp/input/rgsp-stick-axes.sh device/roc/rgsp/rgsp-input-bringup.rc device/roc/rgsp/rgsp-input-prepare.sh device/roc/rgsp/rgsp-kmsg-start.sh device/roc/rgsp/rgsp-wifi-adb-session.sh
# BSP resolves inherited copies late; the first destination wins.
PRODUCT_COPY_FILES := \
    device/roc/roc_os_release_candidate/configs/h700-auto-display.json:vendor/etc/dispconfigs/h700-rgsp-lcd.json \
    device/roc/roc_os_release_candidate/configs/rgsp_fix63_graphics.rc:system/etc/init/rgsp_fix63_graphics.rc \
    device/roc/rgsp/prebuilts/local/mali_kbase.ko:vendor/modules/mali_kbase.ko \
    device/roc/roc_os_release_candidate/configs/roc-source64-startup.rc:system/etc/init/roc-source64-startup.rc \
    device/roc/roc_os_release_candidate/configs/h700-usb-configfs.rc:system/etc/init/h700-usb-configfs.rc \
    device/roc/roc_os_release_candidate/configs/roc-audio-interface.rc:vendor/etc/init/roc-audio-interface.rc \
    device/roc/roc_os_release_candidate/configs/roc-user-build.txt:system/etc/roc-user-build.txt \
    device/roc/roc_os_release_candidate/configs/retired-service.rc:system/etc/init/h700-network-validation-defaults.rc \
    device/roc/roc_os_release_candidate/configs/retired-service.rc:system/etc/init/rgsp-wallpapers.rc \
    device/roc/roc_os_release_candidate/configs/retired-service.rc:vendor/etc/init/rgsp-stick-axes.rc \
    device/roc/roc_os_release_candidate/configs/retired-service.rc:vendor/etc/init/rgsp-input-bringup.rc \
    device/roc/roc_os_release_candidate/configs/retired-helper.sh:system/bin/h700-network-validation-defaults.sh \
    device/roc/roc_os_release_candidate/configs/retired-helper.sh:system/bin/rgsp-wallpapers.sh \
    device/roc/roc_os_release_candidate/configs/retired-helper.sh:vendor/bin/rgsp-stick-axes.sh \
    device/roc/roc_os_release_candidate/configs/retired-helper.sh:vendor/bin/rgsp-input-prepare.sh \
    device/roc/roc_os_release_candidate/configs/retired-helper.sh:vendor/bin/rgsp-kmsg-start.sh \
    device/roc/roc_os_release_candidate/configs/retired-helper.sh:system/bin/rgsp-wifi-adb-session.sh \
    device/roc/roc_os_release_candidate/configs/roc-user-input.rc:vendor/etc/init/roc-user-input.rc \
    device/roc/roc_os_release_candidate/configs/default-permissions-roc-setup.xml:system/etc/default-permissions/default-permissions-roc-setup.xml \
    device/roc/roc_os_release_candidate/configs/leanback.sha256:system/etc/rgsp/leanback.sha256 \
    $(PRODUCT_COPY_FILES)
PRODUCT_PACKAGES := $(filter-out ROCProvisioning rgsp_kmsg_logger,$(PRODUCT_PACKAGES))
PRODUCT_PACKAGES := $(filter-out CtsShimPrivPrebuilt CtsShimPrebuilt,$(PRODUCT_PACKAGES))
GLOBAL_REMOVED_PACKAGES += CtsShimPrivPrebuilt CtsShimPrebuilt
PRODUCT_PACKAGES += ROCReleaseProvisioning roc-power-release ROCReleaseLid
PRODUCT_PACKAGES := $(filter-out H700Lid,$(PRODUCT_PACKAGES))
GLOBAL_REMOVED_PACKAGES += H700Lid
GLOBAL_REMOVED_PACKAGES += ROCProvisioning rgsp_kmsg_logger
PRODUCT_SYSTEM_DEFAULT_PROPERTIES := ro.roc.user.candidate=rc5 $(PRODUCT_SYSTEM_DEFAULT_PROPERTIES)
PRODUCT_NAME := roc_os_release_candidate
# Use the guarded H700 board configuration and internal device identity.
PRODUCT_DEVICE := roc_os_source64
PRODUCT_MODEL := ROC OS
PRODUCT_PACKAGES := $(filter-out AT4K,$(PRODUCT_PACKAGES))
PRODUCT_PACKAGES += ROCReleaseLauncher
GLOBAL_REMOVED_PACKAGES += AT4K
ifeq ($(TARGET_PRODUCT),roc_os_release_candidate)
ifneq ($(TARGET_BUILD_VARIANT),user)
$(error ROC release candidate requires user variant)
endif
ifeq ($(strip $(ROC_RELEASE_KEYS_DIR)),)
$(error ROC_RELEASE_KEYS_DIR must point to separately managed private release keys)
endif
ifeq ($(filter /%,$(ROC_RELEASE_KEYS_DIR)),)
$(error ROC_RELEASE_KEYS_DIR must be an absolute Linux path)
endif
roc_required_key_files := releasekey platform shared media networkstack
$(foreach k,$(roc_required_key_files),$(if $(wildcard $(ROC_RELEASE_KEYS_DIR)/$(k).pk8),,$(error Missing $(k).pk8)))
$(foreach k,$(roc_required_key_files),$(if $(wildcard $(ROC_RELEASE_KEYS_DIR)/$(k).x509.pem),,$(error Missing $(k).x509.pem)))
# Old Soong's APEX parser rejects absolute paths even for its fallback lookup.
# The preparer creates this guarded directory symlink in Native only. Key bytes
# remain outside both source trees; nothing under this link is committed.
PRODUCT_DEFAULT_DEV_CERTIFICATE := device/roc/roc_os_release_candidate/.private-signing/releasekey
# BoardConfigCommon replaces ordinary assignments after product parsing. Keep
# its audited private directory and append only the candidate certificate map.
override BOARD_PLAT_PRIVATE_SEPOLICY_DIR := device/softwinner/common/sepolicy/private device/roc/roc_os_release_candidate/sepolicy/private
endif
