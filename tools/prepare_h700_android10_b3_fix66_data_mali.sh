#!/bin/sh
set -eu

export RGSP_STAGE=A10-B3-FIX66-DATA-MALI
export RGSP_RAMDISK_SHA=ce89ea7ef0cfb26f5cc60f7e9ce710bac1c6be55b17a0a7fafc744b37b28a07b
export RGSP_RAMDISK_SIZE=2605108
export RGSP_RAMDISK_NAME=ramdisk-a10-handoff-fix66.gz
export RGSP_HWC_SOURCE=hwcomposer.cupid.fix64.so
export RGSP_PAYLOAD_MANIFEST=fix66-payload.sha256
export RGSP_SOFTWARE_VSYNC=true
export RGSP_EGL_XZ_SOURCE=libGLES_mali.arm32.r20p0.so.xz
export RGSP_MALI_MODULE_XZ_SOURCE=mali_kbase.h700.r20p0.ko.xz

exec sh /mnt/sdcard/prepare_h700_android10_b3_fix63_graphics.sh
