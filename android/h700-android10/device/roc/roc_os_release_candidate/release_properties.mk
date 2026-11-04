# Apply after the Source64 product, in a separate user candidate only.
# This property overlay does not certify SELinux, signatures or boot security.
roc_release_keys := ro.secure ro.adb.secure ro.debuggable persist.sys.usb.config service.adb.tcp.port persist.adb.tcp.port
roc_release_patterns := $(foreach p,$(roc_release_keys),$(p)=%)
PRODUCT_PROPERTY_OVERRIDES := $(filter-out $(roc_release_patterns),$(PRODUCT_PROPERTY_OVERRIDES))
PRODUCT_DEFAULT_PROPERTY_OVERRIDES := $(filter-out $(roc_release_patterns),$(PRODUCT_DEFAULT_PROPERTY_OVERRIDES))
PRODUCT_SYSTEM_DEFAULT_PROPERTIES := $(filter-out $(roc_release_patterns),$(PRODUCT_SYSTEM_DEFAULT_PROPERTIES))
PRODUCT_SYSTEM_DEFAULT_PROPERTIES += ro.secure=1 ro.adb.secure=1 ro.debuggable=0 persist.sys.usb.config=none service.adb.tcp.port=-1 persist.adb.tcp.port=-1
PRODUCT_PACKAGES := $(filter-out su Superuser,$(PRODUCT_PACKAGES))
GLOBAL_REMOVED_PACKAGES += su Superuser
