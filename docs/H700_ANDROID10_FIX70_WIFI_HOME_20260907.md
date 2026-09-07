# Fix70 Wi-Fi And AT4K HOME

Date: 2026-09-07. Target: this calibrated RGSP/H700 only, no analog sticks.

## Verified On Hardware

- Fix69 TF2 system/vendor booted via the protected Fix67 handoff.
  `sys.boot_completed=1`; existing Android data and the installed AT4K APK survived.
- `tools/set_rgsp_home.sh at4k` passed at 11:34. Default HOME resolves to
  `com.overdevs.at4k/.MainActivity`. Launcher3 remains installed for recovery.
  No accessibility grant or privileged APK installation was used.
- Fix70 HAL/init installed at 11:50 with original-file backup and SHA-256 gates.
  Vendor was remounted read-only afterwards.
- At 11:51, two disable/enable cycles succeeded without manual `insmod`
  or property intervention between cycles. HAL and supplicant were running;
  `wlan0` and `p2p0` existed and the framework reached `StaEnabledState`.
- Settings displayed actual scan results. Cumulative result counters rose
  from 404 to 430 across the two cycles, not 430 distinct access points.
- Injected Android `BUTTON_B` returned from Wi-Fi Settings to AT4K.
  This supplements, but does not replace, physical button validation.
- At uptime 1197.68 seconds, SurfaceFlinger/system_server were still
  PID 1492/1936; crash buffer was empty. GLES reported ARM Mali-G31,
  OpenGL ES 3.2 r20p0. Software VSYNC remains a known bring-up workaround.

## Root Causes And Changes

The local BSP implementation in
`frameworks/opt/net/wifi/libwifi_hal/wifi_hal_common.cpp:is_wifi_driver_loaded`
returns false when `wlan.driver.status` does not exist, before inspecting
`/proc/modules`. Preloading the module without initializing that property
therefore caused a duplicate `finit_module` failure (`File exists`).

`init.rgsp.rc` now initializes the property to `unloaded` in early-init.
This does not fake a loaded driver: the actual module table is still checked.

The same BSP reload path waits for `wlan0/p2p0`, but the stock module's
default secondary interface was `wlan1`. Both init and the compiled
`WIFI_DRIVER_MODULE_ARG` now use `if2name=p2p0`. No Wi-Fi framework or
supplicant replacement was needed.

`m -j4 libwifi-hal vendorimage` completed successfully. Installed files:

| File | SHA-256 |
| --- | --- |
| `/vendor/lib/libwifi-hal.so` | `9b88a56176b190a0bcada45e2571742d9f5cab8ffa66557bb0edb940c9e0a7e3` |
| `/vendor/etc/init/init.rgsp.rc` | `72b4fc47d8e68203fa4f45578d250b91f7578c854963e2808e7217f09edf8506` |

Original files are retained at `/rgsp-persist/fix70-wifi-backup/`.
`tools/install_rgsp_wifi_fix70.sh` is a guarded, first-install migration
for the recorded card CIDs and old file hashes, not a generic fleet updater.
The updated init file will only be parsed on the next Android boot;
this session emulated its property initialization before testing the new HAL.

## Evidence

Local UART evidence under `out/logs/uart/rgsp/`:

- `rgsp_uart_fix36_20260907_113149_115200.log`: handoff and Android boot.
- `rgsp_serial_exec_20260907_113445_115200.log`: HOME switch.
- `rgsp_serial_exec_20260907_113941_115200.log`: duplicate load failure and recovery hashes.
- `rgsp_serial_exec_20260907_114258_115200.log`: original reload timeout.
- `rgsp_serial_exec_20260907_115057_115200.log`: guarded installation passed.
- `rgsp_serial_exec_20260907_115117_115200.log`: two Wi-Fi cycles and HOME resolver.
- `rgsp_serial_exec_20260907_115220_115200.log`: return, GPU and core PID checks.
- `rgsp_serial_exec_20260907_115357_115200.log`: Wi-Fi UI and focus.

Raw logs/UI trees can contain nearby SSIDs and remain local, outside Git.
Network passwords must not be written into tracked scripts, docs or manifests.
The user-supplied APK and proprietary deployment binaries remain local.

## Recovery And Boundaries

Launcher recovery from an Android root shell:

```sh
sh /rgsp-persist/set_rgsp_home.sh launcher3
```

Switch back using `at4k` only after the verified APK is installed.
The repository version bounds `am start -W` with a 15-second timeout;
the successfully deployed HOME script predates that timeout-only refinement.

The Windows TF2 writer did not touch TF1. The subsequent protected handoff
temporarily wrote TF1 boot and restored it before Android userspace.
Android-side recheck matched the original boot hash
`d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`
and environment first-128-KiB hash
`d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`.
No explicit U-Boot/environment write was issued; the vendor boot log
does report its own automatic boot0 DRAM update.

Not yet qualified:

1. User AP selection/password entry, authentication, DHCP, DNS, HTTPS,
   disconnect/reconnect and saved-network recovery.
2. Full reboot with the new init and persistence of default HOME.
3. All physical AT4K focus paths, Settings shortcut and DPAD keyboard.
4. TF2 standalone cold boot. Current startup still depends on TF1 Linux
   and the protected one-shot handoff; ordinary reboot returns to Linux.
5. Clean-data installation, 60-minute stability, ten cold boots,
   SELinux enforcing/security, audio/power/Bluetooth and multi-model input.

SDIO retry/RTO messages and missing optional Wi-Fi offload requests still
appear during toggling. Successful scan does not prove those paths,
P2P, hotspot, power saving or advanced HAL features work.

## Deployment Reproduction

Keep the Fix69 package unchanged. A new Fix70 package is generated with:

```sh
sudo python3 tools/prepare_rgsp_wifi_deployment.py \
  --workspace /mnt/d/Works/H700Android \
  --output /mnt/d/Works/H700Android/out/rgsp-fix70-wifi-deployment \
  --wifi-fix70 /mnt/d/Works/H700Android/out/rgsp-fix70-wifi-home
```

The composer validates both fixed artifact hashes before mounting any image,
retains Fix67 GPU/LCD/input repairs, and records overrides in the manifest.
It does not write the device or change existing Fix69 provenance.
Seven deployment-helper tests and the RGSP Wi-Fi asset checks passed.
The package completed at 11:58. Both ext4 checks passed. Read-only comparison
against Fix69 found zero system file changes and exactly two vendor file
changes: `etc/init/init.rgsp.rc` and `lib/libwifi-hal.so`. Raw hashes differ
because filesystem metadata is regenerated as well as the two vendor files.

| Artifact | SHA-256 |
| --- | --- |
| `system.raw.img` | `7f0285cfa60a670c9912b5ca141d36d41033ce97024483b74eda235ed85c920b` |
| `vendor.raw.img` | `6be07108cbf0530353b0f55b9d6b3f05bdef849f40273e7bd3c8a33bc1b0d5dd` |

This package predates Fix71 keyboard work and does not contain LeanbackIME
or AT4K's later per-user compact-layout preference. Do not relabel it as Fix71.
