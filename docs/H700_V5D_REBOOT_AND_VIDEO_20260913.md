# H700 v5d Physical Reboot Failure And Video Review

Date: 2026-09-13, Asia/Shanghai.
Latest request: inspect the supplied camera video for flicker causes.
Permanent boot deployment and reboot regression were interrupted by that
request and remain pending. Do not claim the reboot issue is fully fixed.

## Physical Reboot Failure

The user reports successful first boot of v5d, persistent flicker, then
a reboot stuck before the Android logo. COM4 is the verified CH343 adapter.
The device was in the ramdisk `/ #` rescue shell, not Android.

Read-only ARM dosfstools 4.2 on the unmounted ROMS partition reported:

```text
65:01/00
Dirty bit is set. Fs was not properly unmounted and some data may be corrupt.
Free cluster summary wrong (2957351 vs. really 2957350)
/dev/mmcblk0p8: 4 files, 6/2957356 clusters
```

The GPT check passed, p8 already used 96930363904 bytes, and userdata
contained `.rgsp-capacity-v1` but no resize-pending marker.
The original v5d checker correctly refused an out-of-scope diagnostic,
but this exposed inadequate recovery coverage and made ROMS block Android.
The previous shutdown method and why the dirty metadata remained are not
yet established by a captured shutdown trace.

Evidence:

- `out/logs/uart/rgsp/rgsp_serial_exec_20260913_194017_115200.log`
- `out/rgsp-v5d-reboot-failure-20260913/head64.before.bin.gz`
- Captured gzip SHA-256:
  `aad844c1c137ee8a2c01eb837ea9d016521c8dfbf3ce04ce9356cd30b17f92a8`

`tools/rgsp_check_fat.sh` now additionally accepts a stale numeric FSInfo
free count only when the complete read-only FAT scan reports no other
problems, signatures/location match, and the count equals total minus used
clusters. It backs up both sectors, changes only primary byte 65 and/or
four bytes at offset 1000, verifies readback, and requires clean fsck.
It does not change FAT allocation entries, directories or file data.

Thirteen host tests passed, including this actual failure capture, dirty
only, count only, their combination, and refusal of orphan chains or
invalid metadata. The new script was uploaded into RAM with a verified SHA:
`54efdd3567c2c0cc7b9509d59e65e7acf83260e59f0f3fe1ff5e0f8ca8d16528`.
Its execution on the real board succeeded and post-repair fsck was clean:
`out/logs/uart/rgsp/rgsp_serial_exec_20260913_194942_115200.log`.
Repair backups are under userdata `rgsp-fat-dirty-<boot-id>`.

At 20:06 the rescue shell executed `/init` and continued the same kernel
boot into Android. This was NOT a physical reboot regression test.
At 20:11 `sys.boot_completed=1` and serial `5c001089d750c872012` were verified.
Capture: `out/logs/uart/reboot/20260913_200623_ResumeRamdisk.log`.

No boot partition was written, no new full image was built, and the
original v5d image still contains the older dirty-only checker.
Next reboot may encounter the same problem until boot is updated.
Do not reuse v5d as a physically qualified reboot-stable release.

## Camera Video

Input: `C:/Users/LPF/Desktop/2026-09-10 085028.mov`.
Embedded creation time: 2026-09-10 08:50:28 +08:00, not the current v5d session.
Duration 26.7 seconds, 30 FPS, 801 decoded frames, portrait display rotation.
It shows the launcher entering a music player and navigating albums/tracks.
Do not copy unrelated camera location metadata into reports.

Analysis artifacts: `out/flicker-video-20260913/`.
`tools/analyze_rgsp_flicker_video.py` saves one-second overview frames,
0.1-second screen-region contact sheets and every-frame ROI luminance.
The fixed ROI is only a screening aid: perspective, reflections, content
and camera exposure prevent it from measuring actual backlight output.

No repeated whole-screen blackouts were established in these samples.
Large scene changes coincide with app launch around 4.7 s, list loading
around 6.4 s, navigation around 14.4 s and page change around 24.2 s.
This video cannot establish voltage noise, UART interference, a defective
panel or a particular software fix. User clarification was requested:
is it a stable reference clip, or which interval shows the fault?

Current live read-only power evidence at 20:11:
`out/logs/uart/rgsp/rgsp_serial_exec_20260913_201141_115200.log`.
Android was Awake; screen timeout was 60000 ms; the last sleep was `timeout`.
Events show sleep at 20:10:25 and wake at 20:10:41. These events cannot be
time-correlated with the September 10 camera video.

Earlier September 13 evidence documented unsolicited framework
`power_button` sleep/wake, but the raw PMIC capture did not cover that event.
See `H700_V5C_LIVE_TRIAL_20260913.md`; raw input/physical correlation remains
unproven. Keep power-policy blackouts distinct from output/backlight glitches.
No brightness, voltage, panel timing, key mapping or lockscreen changes
were made for this video review. COM4 is closed; no capture process remains.
