# H700 Android 10 A10-B3 path-one status

## 2026-09-06 Fix64 Continuation

Real Android lock-screen, Launcher desktop, and app-drawer screenshots are
now available. GPU/ION app permissions, the still-Homlet WSL display build,
and the ramdisk watchdog executable/root handling were separate failures.
Fix64 also adds an opt-in software VSYNC compatibility path because the H700
kernel's VSYNC uevent producer and framebuffer wait ioctl are not working.

Current evidence, artifact hashes, deployment entry point, and remaining
qualification items are in `H700_ANDROID10_FIX64_VISIBLE_UI_20260906.md`.
The original Fix62 process-presence-only success test was NOT deployed as-is.
The user confirmed the physical desktop matches the screenshot on 2026-09-06.
Full Fix64 reboot and automatic watchdog exit succeeded. Full A10-B4 soak
and cold-start qualification are still pending.

## Result

The vendor U-Boot can be interrupted automatically after temporarily setting
`bootdelay=3`, but its standard `mmc` command has no registered devices. `mmc
list`, `mmc dev 0`, `mmc dev 1` and `mmc dev 2` all report `No MMC device
available`; `ext4ls` is not present. The bootloader only exposes the internal
card through its private `sunxi_flash` path, so direct TF2 loading cannot be
used with the current U-Boot build.

The temporary environment change was restored from
`/mnt/mmc/RGSP_RECOVERY/env-original-pre-fix2.bin` and verified. The device is
back on the original Linux boot image and the protected hashes are unchanged:

```text
TF1 boot: d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
TF1 env head: d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
```

## A10-B3 continuation

The next executable route is the established TF1 temporary handoff. The new
Android 10 handoff boot is built from the verified RGSP kernel/DTB and the
fix32 recovery ramdisk, with an `a10-b3` wrapper that restores TF1 boot before
switching to the Android 10 TF2 system root.

Artifacts:

- `out/h700-android10-b2/h700-android10-b3-handoff-boot.img`
- `out/h700-android10-b2/h700-android10-b3-handoff-boot.img.gz9`
- `tools/prepare_h700_android10_b3.sh`
- `tools/run_h700_android10_b3.ps1`

The compressed boot must be copied to the TF2 `ANBOOT` root before running
`tools/run_h700_android10_b3.ps1`. The script then verifies the copied file,
uploads the small preparation script, checks both cards and filesystem health,
writes TF1 `p4`, creates the one-shot marker, and keeps UART capture active for
the Android init/ADB/zygote/system_server evidence.

## 2026-09-05 UI bring-up status

Fix53 completed the Android 10 boot flow through `BOOT_COMPLETED` and kept the
system alive for the automatic 180-second SysRq recovery window. Fix54 repaired
the pre-existing empty `/data/user/0` directory by replacing it with the
Android 10 compatibility symlink `/data/user/0 -> /data/data`; this removed the
application `EACCES` failures.

Fix55 added the standard `android.software.app_widgets` feature declaration.
`AppWidgetService` now starts and the Launcher3 `AppWidgetManager=null` crash
is gone. The remaining visible-screen blocker is independent: SystemUI's
RenderThread aborts in `libhwui.so:EglManager::damageFrame()`, so the next step
is a minimal EGL/Mali compatibility fix (fix56) followed by another automatic
180-second UART test.
