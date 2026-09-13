# H700 Android Direct Flash Canonical Path

> Baseline clarification, 2026-09-13: the command chain below is historical
> v5/v5b success evidence, not a newly qualified v5c writer. Three later v5c
> attempts failed; the current card was flashed with Rufus and subsequently
> reached the desktop. Read `H700_V5C_RUFUS_BOOT_HANDOFF_20260913.md` and
> `H700_V5C_USER_ACCEPTANCE_20260913.md` first. Re-audit the PowerShell runtime
> and rediscover the target before any future write. Do not execute this
> historical command as part of the current UART-only validation.

## Current status

As of **2026-09-13**, the canonical physical-card flashing method is the
full-image direct writer below. It was used successfully on the same USB
reader/card identity for the v5 and v5b images, with complete physical-drive
readback and matching SHA-256 values.

Do not use the old segmented v3b writer, `burn_v4_fast.ps1`, or a project
card-writing wrapper for this workflow. Rufus remains a distribution option,
but it is slower and its progress does not replace a controlled readback.

## Proven command chain

Run an elevated PowerShell terminal and execute:

```powershell
cd D:\Works\H700Android
$run = "D:\Works\H700Android\out\rgsp-v5c-direct-flash-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $run | Out-Null
PowerShell -NoProfile -ExecutionPolicy Bypass -File `
  D:\Works\H700Android\tools\direct_flash_v5.ps1 `
  -ImagePath D:\Works\H700Android\out\H700_Android_SingleCard_v5c_SettingsDpad.img `
  -DiskNumber 3 -RunDirectory $run
```

The script is intentionally restricted to the approved removable disk:

- Disk number: `3`
- USB serial: `000000001539`
- Physical size: `125069950976` bytes
- Image size: `32434554368` bytes
- Manifest status: `OFFLINE_VERIFIED_READY_FOR_FLASH`

If any identity, size, boot/system-disk, read-only, or manifest check fails,
stop. Do not substitute another disk number based only on a drive letter.

## What the successful writer does

1. Validates the image size and sibling JSON manifest.
2. Identifies Disk 3 by USB serial, exact byte capacity, and non-boot/system
   status.
3. Locks and dismounts every exposed volume on the card.
4. Opens `\\.\PhysicalDrive3` exclusively with administrator rights.
5. Clears the physical tail to retire stale larger-card GPT data.
6. Writes the complete image from byte 0 and flushes it.
7. Reopens the physical disk read-only and hashes exactly the image length.
8. Requires the readback SHA-256 to equal the manifest hash.
9. Closes all handles and records `result.json` and `direct-flash.log`.

The result is valid only when `result.json` contains
`DIRECT_WRITE_AND_READBACK_VERIFIED`. That status confirms media contents,
not physical boot; UART and TF1 cold-boot testing remain separate acceptance
steps.

## Known historical failures

The removed failed logs were tooling attempts, not evidence that the v5 image
was invalid:

- The segmented writer assumed a smaller fixed card and repeatedly hit target
  identity or raw-write permission failures.
- A first v5 writer failed while trying to offline removable media, which
  Windows does not support; the successful writer instead locks and dismounts
  all volumes.
- Repeated concurrent attempts created misleading partial stage logs.
- Rufus completed slowly but did not provide the same controlled physical
  readback record.

The retained successful evidence is:

- `out/rgsp-v5-direct-flash-20260912-224130/`
- `out/rgsp-v5b-direct-flash-20260913-002430/`
- `tools/direct_flash_v5.ps1`
- `tools/RgspVolumeLock.cs`

## Current v5c image

```text
Image:  H700_Android_SingleCard_v5c_SettingsDpad.img
Bytes:  32434554368
SHA256: cf481773dd2658a0a7307222f2a19679fd74c88a53923a0d72a13bfe7ef711cb
```

This image includes the Settings D-pad focus fix while retaining the proven
v5b boot, TV UI, AT4K layout, data filesystem, and capacity expansion path.

## Post-write handoff

After `DIRECT_WRITE_AND_READBACK_VERIFIED`:

1. Keep the reader connected until the result is recorded.
2. Use Windows safe removal or the script's eject result.
3. Insert the card into TF1, with TF2 removed.
4. Capture UART from power-on at 115200 baud.
5. Accept physical boot only after Android reaches the UI and
   `sys.boot_completed=1` is observed.
