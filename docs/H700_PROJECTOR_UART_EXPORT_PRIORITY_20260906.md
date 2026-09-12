# H700 Projector UART Export Priority

Date: 2026-09-06
Target: H21S-700-V3.0 projector board
Purpose: collect read-only donor data for RGSP H700 Android 10 bring-up.

## P0: collect first

1. Start the UART capture before applying power. Use `115200 8N1`, board TX to
   USB-TTL RX, board GND to USB-TTL GND, and leave VCC disconnected.
2. Capture one complete cold boot until `sys.boot_completed=1` and keep the
   raw transcript. A second capture after an Android `reboot` is useful for
   comparing cold and warm boot paths.
3. Once the Android shell is available, save these text snapshots:

```sh
date
getprop
cat /proc/cmdline
cat /proc/version
cat /proc/cpuinfo
cat /proc/meminfo
cat /proc/partitions
mount
df -hT
blkid 2>/dev/null || true
ls -l /dev/block/by-name 2>/dev/null || true
cat /sys/block/mmcblk0/device/cid 2>/dev/null || true
```

These establish the exact Android version, kernel, RAM, storage topology,
PARTUUIDs, logical partitions and boot arguments.

## P1: files that directly help the RGSP port

Export the following file trees and preserve their SHA-256 hashes:

```text
/vendor/etc/init/
/system/etc/init/
/vendor/etc/vintf/
/system/etc/vintf/
/vendor/etc/firmware/
/vendor/etc/
/vendor/bin/hw/
/vendor/lib/hw/
/vendor/lib64/hw/
/vendor/lib/egl/
/vendor/lib64/egl/
/system/lib/egl/
/system/lib64/egl/
```

The highest-value individual files are:

```text
vendor/etc/vintf/manifest.xml
vendor/etc/init/*.rc
vendor/etc/fstab.*
vendor/etc/ueventd*.rc
vendor/etc/selinux/*contexts*
vendor/lib*/egl/libGLES_mali.so
vendor/lib*/hw/gralloc*.so
vendor/lib*/hw/hwcomposer*.so
vendor/lib*/hw/android.hardware.graphics*.so
vendor/lib*/libion*.so
vendor/bin/hw/android.hardware.graphics* 
vendor/bin/hw/android.hardware.audio*
vendor/bin/hw/android.hardware.wifi*
vendor/etc/audio*.xml
vendor/etc/*mixer*.xml
vendor/etc/firmware/*8821* /vendor/etc/firmware/*wifi*
```

For every copied binary, also collect `file`, `readelf -h`, `readelf -d` and
`sha256sum` output. The goal is to compare complete ABI groups, especially:

```text
mali_kbase.ko
+ libGLES_mali.so
+ Gralloc/allocator/mapper
+ HWC/composer
+ libion
+ /dev/mali0 /dev/ion /dev/disp
```

Do not copy only `libGLES_mali.so` and assume it is sufficient.

## P1: runtime evidence

Run these after Android has reached the shell. Redirect large output to files
on removable storage or a network-mounted destination rather than flooding the
UART terminal.

```sh
uname -a
ls -l /dev/mali* /dev/ion /dev/disp /dev/fb* /dev/dri/* 2>/dev/null || true
cat /proc/fb 2>/dev/null || true
cat /sys/module/mali_kbase/version 2>/dev/null || true
cat /proc/modules
dmesg | grep -Ei 'mali|disp|fb|ion|drm|lcd|dsi|hdmi|audio|codec|wifi|bluetooth|mmc'
dumpsys SurfaceFlinger 2>/dev/null || true
dumpsys media.audio_flinger 2>/dev/null || true
dumpsys media.audio_policy 2>/dev/null || true
cat /proc/asound/cards 2>/dev/null || true
cat /proc/asound/pcm 2>/dev/null || true
dumpsys wifi 2>/dev/null || true
getevent -lp 2>/dev/null || true
dumpsys input 2>/dev/null || true
service list 2>/dev/null || true
ps -A 2>/dev/null || ps 2>/dev/null || true
logcat -b all -d -v threadtime 2>/dev/null || true
```

These data are useful for matching H700 runtime service names, graphics
initialization order, audio card naming, Wi-Fi service behavior and Android
input discovery.

## P2: binary donor extraction

If ADB, SSH or external storage is available, prioritize these raw or staged
files before attempting a complete eMMC image:

```text
boot partition image
vbmeta, vbmeta_system and vbmeta_vendor
DTB/DTBO from the boot image
mali_kbase.ko and related kernel modules
vendor image or an extracted vendor directory
```

The `super` partition is useful, but it is large. Exporting the complete
`vendor` content and boot/DTB first usually gives more value per byte for the
current RGSP work.

## Do not do yet

- Do not write to boot0, boot1, GPT, U-Boot environment or any partition.
- Do not run `dd if=/dev/mmcblk0 of=...` before confirming destination space.
- Do not copy the projector bootloader, DTS, PMIC, MS7200, motor or HDMI
  configuration into RGSP.
- Do not use `selinux=permissive` or `buildvariant=eng` as the RGSP product
  security configuration.

The existing Windows UART capture tool can be used for the raw transcript:

```powershell
.\tools\capture_rgsp_uart.ps1 -Port COMx
```

For an interactive shell, the serial command helper can be used with the
projector port and a longer timeout, but its output directory should be changed
to `out/logs/uart/projector-h21s700` so that projector and RGSP captures remain
separate.
