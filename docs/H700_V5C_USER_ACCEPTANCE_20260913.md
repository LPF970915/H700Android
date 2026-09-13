# H700 v5c User Acceptance and Next Diagnostics

Date: 2026-09-13, Asia/Shanghai.
Candidate: `out/H700_Android_SingleCard_v5c_SettingsDpad.img`.
Context: user-reported Rufus flash, followed by this thread's UART capture.

## Current Verdict

The user confirms that Android reaches the desktop and displays AT4K.
Physical directional input works and Settings supports basic up/down
navigation. This supersedes the earlier UI-unverified checkpoint, but does
not qualify all Settings pages or the complete no-touch workflow.

No automatic reboot, black screen or freeze was observed by the user during
this run. This is not a formal soak or repeated cold-boot qualification.
The image manifest remains unchanged; no new full-card readback or on-device
component identity check was performed in this diagnostic pass.

## User-Reported Results

| Area | Result |
| --- | --- |
| Android desktop and AT4K | Visible; boot-to-desktop confirmed by user |
| Physical directional keys | Basic navigation works |
| AT4K menu | D-pad scrolling still unavailable |
| Settings | Basic up/down works; language selection remains blocked |
| Language | Simplified Chinese can be added, but cannot be focused/selected to switch |
| DocumentsUI / Files | D-pad focus navigation unusable; package/activity relationship not yet checked |
| Wi-Fi password | A moves focus downward instead of opening the keyboard; connection not tested |
| Audio | Not tested on this candidate; user has no test app installed |
| ROMS read/write | Not tested |
| Storage display | User sees total 32G, available 16.17; exact screen/volume not yet identified |
| Runtime stability | No reboot, black screen or freeze observed by user |

## Storage: Separate Geometry From Android Exposure

UART evidence:
`out/logs/uart/rgsp/rgsp_uart_20260913_124539_115200.log`.

The current boot reports:

```text
ROMS_BYTES=96930363904
FAT_GROW old_sectors=8388576 new_sectors=189317116
FAT_GROW_COMPLETE
FAT_ALREADY_FULL
[rgsp-grow] partition and filesystem capacity verified
```

This is evidence that the boot helper reported a roughly 96.93 GB
(90.27 GiB) ROMS partition and completed FAT growth. It does not establish
application access, current Android volume registration or file persistence.
The product allocates a separate 16 GiB data partition; expanding ROMS does
not expand app-install storage.

Local source `tools/rgsp_single_card_init.sh` mounts p8 as vfat and binds it
to `/rgsp-persist`. The inspected RGSP `fstab.sun50iw9p1` has system, vendor,
data and zram entries, but no ROMS `voldmanaged` entry.
Missing Android shared-volume exposure is therefore a concrete investigation
lead, not a confirmed complete runtime diagnosis. Check the packed/runtime
configuration and StorageManager/vold state before changing mount ownership.
Do not mount the same writable FAT volume independently through two owners.
Do not format, re-expand or resize data based on the Settings capacity label.

## Input: Evidence and Unknowns

The local RGSP keylayout maps physical scan code 304 to ENTER. The existing
LeanbackIME patch handles ENTER for RGSP with scan code 304 (or injected
device ID -1), and requires a valid editable input connection to request
the keyboard. Its presence in source is not proof that this running IME
receives the physical event or contains the intended patch.

First check active IME, APK provenance, firstboot status, physical event
mapping and focused editor. Do not equate injected-key tests with physical
button acceptance, change global A mapping blindly, or overwrite user
language/HOME/IME preferences as a diagnostic shortcut.

Settings language ordering, DocumentsUI focus and AT4K menu scrolling are
separate UI paths. TV mode and the homepage focus fix do not qualify them.

## Next Work, In Order

1. Preserve this boot's UART and user observations; identify the exact
   storage screen showing 32G and the focused Wi-Fi password field.
2. Obtain read-only runtime evidence: boot completion, active HOME/IME,
   relevant APK hashes, firstboot marker/status, physical input routing,
   current mounts, p8 size, filesystem capacity and Android volume lists.
   Avoid collecting passwords or saved network credentials.
3. Restore physical A-to-keyboard entry in Wi-Fi with a narrowly scoped fix;
   verify open, type, delete, dismiss and reopen with physical buttons.
4. Make Settings language ordering/selection and DocumentsUI navigation
   usable without touch, then complete the APK install/permission workflow.
5. Resolve ROMS exposure through the appropriate Android storage integration,
   preserving diagnostic logging. Verify app access, a dedicated test file
   and persistence after an agreed normal reboot.
6. Fix AT4K menu focus/scrolling and recheck the lowest off-screen items.
7. Recheck Wi-Fi connection, audio, power/brightness and sleep/wake on v5c;
   then perform the planned 60-minute soak and 10 cold boots.

Implementation acceptance must include physical-button checks and persistent
storage checks, not just successful builds or APK presence.
No device commands, card writes, formatting, reboot, firmware build, user
preference changes or global key remapping were performed for this record.
