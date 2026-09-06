#!/bin/sh
set -eu

export RGSP_STAGE=A10-B3-FIX67-FRAMEWORK-TRIGGER
export RGSP_RAMDISK_SHA=8160e3a4f4f96a9b6985969003529263ce98a7719c6eb729b0a790a4bc16babd
export RGSP_RAMDISK_SIZE=2605108
export RGSP_RAMDISK_NAME=ramdisk-a10-handoff-fix67.gz
export RGSP_HWC_SOURCE=hwcomposer.cupid.fix64.so
export RGSP_PAYLOAD_MANIFEST=fix67-payload.sha256
export RGSP_SOFTWARE_VSYNC=true
export RGSP_EGL_XZ_SOURCE=libGLES_mali.arm32.r20p0.so.xz
export RGSP_MALI_MODULE_XZ_SOURCE=mali_kbase.h700.r20p0.ko.xz

exec sh /mnt/sdcard/prepare_h700_android10_b3_fix63_graphics.sh
