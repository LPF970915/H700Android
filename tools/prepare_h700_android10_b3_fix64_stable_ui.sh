#!/bin/sh
set -eu

export RGSP_STAGE=A10-B3-FIX64-STABLE-UI
export RGSP_RAMDISK_SHA=e5f0dab04fdfb7945030b4f2a1265ec2496cc967e3ededa278e808c19284c2fc
export RGSP_RAMDISK_SIZE=2604992
export RGSP_RAMDISK_NAME=ramdisk-a10-handoff-fix64.gz
export RGSP_HWC_SOURCE=hwcomposer.cupid.fix64.so
export RGSP_PAYLOAD_MANIFEST=fix64-payload.sha256
export RGSP_SOFTWARE_VSYNC=true

exec sh /mnt/sdcard/prepare_h700_android10_b3_fix63_graphics.sh
