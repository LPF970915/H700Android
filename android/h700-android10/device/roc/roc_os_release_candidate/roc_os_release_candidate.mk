# Isolated user candidate; never substitute the live eng product/output.
$(call inherit-product, device/roc/roc_os_source64/roc_os_source64.mk)
include $(dir $(lastword $(MAKEFILE_LIST)))release_properties.mk
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
endif
