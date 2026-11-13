# Apply after the Source64 product, in a separate user candidate only.
# This property overlay does not certify SELinux, signatures or boot security.
roc_release_keys := ro.secure ro.adb.secure ro.debuggable persist.sys.usb.config service.adb.tcp.port persist.adb.tcp.port
roc_release_patterns := $(foreach p,$(roc_release_keys),$(p)=%)
PRODUCT_PROPERTY_OVERRIDES := $(filter-out $(roc_release_patterns),$(PRODUCT_PROPERTY_OVERRIDES))
PRODUCT_DEFAULT_PROPERTY_OVERRIDES := $(filter-out $(roc_release_patterns),$(PRODUCT_DEFAULT_PROPERTY_OVERRIDES))
# Inherited property lists expand late; uniq-pairs keeps the FIRST value.
PRODUCT_SYSTEM_DEFAULT_PROPERTIES := ro.secure=1 ro.adb.secure=1 ro.debuggable=0 persist.sys.usb.config=none service.adb.tcp.port=-1 persist.adb.tcp.port=-1 $(filter-out $(roc_release_patterns),$(PRODUCT_SYSTEM_DEFAULT_PROPERTIES))
PRODUCT_PACKAGES := $(filter-out su Superuser,$(PRODUCT_PACKAGES))
GLOBAL_REMOVED_PACKAGES += su Superuser

# Match the official 0.0.2 card identity without changing the Android API version.
PRODUCT_SYSTEM_DEFAULT_PROPERTIES := ro.roc.os.version=0.0.2 $(filter-out ro.roc.os.version=%,$(PRODUCT_SYSTEM_DEFAULT_PROPERTIES))
override BUILD_DISPLAY_ID := ROC_OS_ARM64_ver0.0.2
