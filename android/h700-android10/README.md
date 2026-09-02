# H700 Android 10 Mainline

This directory is the clean product baseline for RGSP-class H700 handhelds.

Implementation sources:

- Android 10 / API 29 from the complete H616 source archive.
- Allwinner `sun50iw9p1` / `cupid` HALs from the H616 tree.
- The RGSP H700 kernel, DTB, panel, PMIC, input and storage facts.

Reference only:

- The frozen R36S Android 11 bring-up branch.
- The selected H618 Android 12 files under `reference/h618-android12`.

The initial product is 32-bit userspace on the existing AArch64 kernel, with
64-bit Binder, flattened APEX, low-RAM configuration and no GMS. A dual-ABI
profile may be added only after the 32-bit product reaches a stable launcher.

Do not import an Orange Pi bootloader, whole DTS, PMIC configuration, partition
table, projector services or television product overlay. `cupid` and the H616
board selector are retained only to select the compatible Android 10 HAL family;
the product identity, kernel and DTB remain H700/RGSP.

The product deliberately does not inherit `device/softwinner/cupid-common/
cupid-common.mk`, because that file adds HDMI-CEC, AC100/HDMI audio, PPPoE,
PlayReady/Widevine and television defaults. Required H616 components are listed
explicitly in `device/roc/h700-common/device.mk`.

## Bring-up order

1. Reproduce the Android 10 source build.
2. Boot the existing RGSP kernel and DTB with the Android 10 ramdisk.
3. Mount TF2 system, vendor and data using the recorded PARTUUIDs.
4. Reach init, ADB, zygote and an unmodified system_server.
5. Enable the H616 Mali-G31, Gralloc, HWC2 and ION stack.
6. Adapt the 720x480 panel and physical controls.
7. Enable H616 audio against H700 `audiocodec` card 0/device 0.
8. Add AXP2202 health, power, lights, Hall, rumble and wireless support.

The files here are a product overlay scaffold. They are not a flashable image.
The active execution plan is `docs/H700_ANDROID10_NEXT_DEVELOPMENT_PLAN_20260902.md`.
