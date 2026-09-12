# QQ Music Playback: Audio HAL Failure

Date: 2026-09-10. Host timezone Asia/Shanghai; device logs use UTC.
Status: persistent vendor deployed; September 10 warm-boot software playback
passed; user confirmation of post-reboot audible output pending.

## Latest Acceptance

The replacement session completed guarded Audio startup and the full
23-component runtime check at 17:12. Sound-node ownership/mode was correct
without live repair, all audio files matched the deployed candidate, and
no temporary overlays or service restarts were needed. A low-amplitude
two-second probe drained 96000 frames at volume 3/15.

At 17:28-17:29 QQ Music had an active playing session and active speaker
track; PCM was RUNNING with hardware pointers advancing across two samples.
Audio HAL/audioserver retained PIDs 1495/1503, and the crash buffer was empty.
The device is left playing for user audible confirmation. This is not yet
acoustic, headphone, HDMI, cold-boot or formal soak acceptance.
Full evidence and remaining startup caveats are recorded in
`H700_ANDROID10_AUDIO_STARTUP_RECOVERY_20260910.md`.
The sections below retain the historical investigation and deployment
checkpoints; their earlier pending states are superseded by dated results.

## Observation

The user launched QQ Music TV and attempted song playback. Physical volume
buttons displayed a medium level, but no sound was heard.

Read-only UART samples at host 08:56-08:58 show:

- STREAM_MUSIC speaker index 11/15, muted false; master mute off.
- Framework output device SPEAKER (0x2), not HDMI or a headset.
- Primary ALSA card 0 is audiocodec, playback device 0. PCM status closed.
- Audio HAL repeatedly crashes while starting output; this is a system
  audio failure, not evidence that the APK alone is incompatible.
- A snapshot between restarts has no tracks and zero frames written.
  It must not be interpreted as proof that the user never pressed play.

## Confirmed Failure Chain

The log repeatedly reports:

```text
audio_platform: platform_init
audio_route: Unable to open the mixer, aborting.
audio_route: invalid audio_route
SIGSEGV / SEGV_MAPERR, fault addr 0x4
audio_route_update_mixer+6
reset_platform_out_path+16
select_devices+380
start_output_stream+60
out_write+264
```

The crashing process is
`/vendor/bin/hw/android.hardware.audio@2.0-service`, using
`/vendor/lib/hw/audio.primary.cupid.so` and the 5.0 implementation.
This is not the old Android 11 fix57 audio-factory crash.

All sampled `/dev/snd` nodes, including controlC0 and pcmC0D0p,
are root:root mode 0600. The HAL has UID 1041 and primary GID 1005
(audio), not root. These node permissions block its normal device access.
Live `/ueventd.rc` line 54 instead specifies:

```text
/dev/snd/* 0660 system audio
```

SELinux is Permissive; permissive AVC messages are not evidence of an
enforcing SELinux denial. Do not change SELinux mode as a proposed fix.

The existing RGSP input preparation script already documents inherited
devtmpfs nodes bypassing ueventd coldboot during Linux-to-Android handoff.
The same lifecycle issue is a plausible explanation for audio node modes,
but it has not yet been independently traced for sound devices.

## Additional Risk

The installed mixer XML contains donor controls such as Speaker Switch and
DAC volume. Live tinymix subsequently confirmed these do not exist. There
are nine controls, including tx hub mode, two gains and six switches.
The speaker trial used the measured switches and passed. Headphones,
HDMI, capture and repeated media-volume changes remain unqualified.

## Next Controlled Test

1. Pause playback and lower media volume before any change that may restore
   output. Do not infer successful pause from the user's earlier report.
2. Record exact device identity, node owner/group/mode and audio service
   state. Temporarily apply the existing ueventd policy only to the required
   card-0 control/playback nodes, with explicit rollback to recorded values.
3. Reinitialize the audio service only as needed, with the scope disclosed.
   Do not reboot or modify system/vendor images for this probe.
4. Read actual mixer controls without changing gains, compare against the
   donor route, and repeat a short low-volume playback test.
5. Verify no new HAL crashes, progressing PCM frames, and user-confirmed
   audible output. Only then prepare persistent startup/config changes.

No permissions, mixer values, volume settings, services, or partition
contents were modified by this diagnostic pass. No test tone was played.
The live trial later corrected only card-0 node permissions, bound a
memory-only speaker route, and played a low-level 440 Hz test tone. The user
confirmed hearing it. The mixer bind mount and six switches were then
rolled back successfully; the underlying vendor image remains unchanged.
The two card-0 node permissions were NOT rolled back, despite the earlier
summary claiming all temporary changes were undone. At 10:27 both still
read system:audio 0660. This is a runtime proof of the speaker path, not yet
a persistent-image acceptance.

## Persistent Candidate Prepared

The RGSP product source now contains:

- `ueventd.rgsp.rc` rules for `/dev/snd/controlC*` and `/dev/snd/pcmC*` as
  `system:audio 0660`.
- `rgsp-input-prepare.sh` applies the same ownership/mode after the Linux
  handoff, because inherited devtmpfs can bypass ueventd coldboot.
- A target-specific `configs/audio_mixer_paths.xml` using eight of the nine
  controls observed from card `audiocodec`, leaving tx hub mode unchanged.
  The common product selects exactly one mixer source for h700_rgsp, instead
  of relying on filtering before Android expands inherited copy entries.

The actual WSL build tree was synchronized and the unique-mixer build
completed at 10:27. Earlier successful builds contained donor files and
were rejected for deployment. The former top-level
`out/rgsp-audio-persistent-20260910.vendor.raw.img` is NOT a qualified image.
The verified build is staged separately in
`out/rgsp-audio-build-verified-20260910/`.

The deployable candidate is derived from the hash-pinned, currently deployed
codec vendor, replacing only mixer XML, ueventd rules and the startup helper.
This preserves all earlier deployed codec/Wi-Fi/display fixes; a raw fresh
build alone is not an approved replacement for the frozen vendor baseline.
No physical flash or reboot acceptance has occurred yet.

## Qualified Flash Candidate

Completed at host 10:32 on September 10, 2026:

- Candidate: `out/rgsp-audio-candidate-20260910/vendor.raw.img`
- Size: 2147483648 bytes.
- SHA256: `9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`
- Rollback baseline: `out/rgsp-fix72-codec-candidate-20260908/vendor.raw.img`
- Baseline SHA256: `1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`
- Build log: `out/logs/build/h700-audio-unique-20260910-102526.log`
- Complete metadata/content comparison confirms exactly three changed files;
  codec, Wi-Fi, display and all other entries remain unchanged.
- Baseline, built image and final candidate strict read-only fsck passed.
- Seven audio packaging tests and eighteen vendor I/O tests passed.
- `tools/invoke_rgsp_audio_vendor_deploy.ps1 -Mode Plan` passed without
  opening any physical device. This wrapper selects an explicit Audio profile
  in the existing transactional writer; the default Codec profile retains
  its original candidate and rollback hashes.

The PC disk inventory contains only internal SATA/NVMe disks. Flashing is
waiting for the user to power off the handheld normally and connect TF2 to
the PC reader. Do not hot-remove the card. Rediscover disk number and verify
exact five-partition geometry before Backup/Apply. The Audio profile requires
a new backup receipt and rejects a backup from the earlier Codec profile.
Only p3 may be written. Never pass this candidate to the old boot helper
without first adding a separately reviewed audio component/hash profile.
No new boot preparation, reboot, TF1 write or physical flash has occurred.

During this work the original 120 GiB full-build free-space gate rejected
execution. Subsequent bounded vendor builds ran via separate systemd units
below that floor, and one earlier two-target repack ran without those units.
Those attempts are not evidence that the original low-pressure wrapper
passed. The final unique-source build used CPU quota 100%, CPUs 0-1,
6 GiB memory limit, 512 MiB swap limit, nice 19 and single-worker settings.
The original wrapper and its space gate were not changed.

## P1 Follow-Up Completed

At 11:58 on September 10, the separately authorized p1 repair completed
using a fresh backup of the post-audio-deployment state. The candidate
changes only 60 metadata bytes and preserves all logical file contents.
Physical p1 readback and an independent read-only FAT check of the exported
readback passed. Full system/audio-vendor and GPT hashes are unchanged.
No other partitions were written. The unresolved-p1 statements below are
historical; see `H700_ANDROID10_P1_AUDIO_REPAIR_20260910.md`.
The card is now ready for Windows safe removal and return to the powered-off
handheld. New device-side startup checks and QQ Music playback remain pending.

## TF2 Reader Inspection And Backup

On September 10, 2026 the user connected TF2 to the PC. Disk 3 was freshly
identified as the 125069950976-byte USB device, with all five partition
GUIDs, sizes and offsets matching. Internal disks 0/1 and the empty reader
slot 2 were excluded. No drive letters were assigned.

An elevated, raw-read-only ANBOOT capture completed at 11:05:16:
`out/tf2-audio-inspect-20260910-110454/`. Its complete readback hash was
`b50f5f58b8b2107444021cffd59d87ca83735cae58d8312bd23d5c70b8588648`.
`fsck.fat -n -v` on this host copy exited 1 and explicitly left it unchanged:

- Boot sector and backup differ at byte 65 (01/00).
- `RGSP_ANDROID_LOGCAT_BOUNDED.log` has a chain longer than its recorded size.
- Dirty bit is set; FSInfo free clusters are 95499 versus counted 95496.
- The previous FAT cluster-geometry failure was not reported.

This is NOT a clean FAT acceptance. No FAT repair, format or restore was
performed. The original Linux recovery image content hash remains pinned
and the one-shot marker is absent.

The new Audio-profile backup completed at 11:15:29:
`out/tf2-audio-backup-20260910-110849/`. Full live system and vendor hashes
matched their pinned baselines, and GPT head/tail, ANBOOT and vendor copies
passed full readback. A subsequent host check verified all receipt hashes.
The ANBOOT hash in this backup is
`ee4b9a7ad5164f2b411f2555b935332dccfda76f321863cf620c31c52a9cc1b6`.
A complete host-side binary comparison found exactly one changed byte
relative to the initial inspection: offset 192993874, 29 -> 2A. This is
byte 18 of the `RGSP-L~1IMG` directory entry, changing its last-access date
from September 9 to September 10. It is consistent with Windows reading the
recovery file between captures; all other bytes are identical. Do not claim
that p1 remained byte-identical throughout the entire PC session. The Apply
protected-range baseline is the newer verified backup, not the first capture.

The writer now accepts the verified volume GUID without assigning a drive
letter, using .NET file access while retaining the recovery and one-shot
gates. Twenty-two vendor I/O tests passed. The initial inspection helper
attempt failed on an omitted destination-offset argument before any copying;
the corrected retry above succeeded. Both attempts remain in `out`.

The boot-only helper now has an explicit `audio` profile pinned to the exact
qualified vendor SHA; frozen/codec defaults and filesystem/rollback gates
remain intact. Twenty boot-only tests passed locally. The runtime checker
adds an explicit Audio profile with the three audio component hashes and
card-0 node permission checks, retaining codec checks. It has passed syntax
checking and host-only manifest tests: 17 Frozen, 20 Codec and 23 Audio
components, with every older check retained and all three new hashes matching
the candidate manifest. The runtime checker now explicitly requires
PowerShell 7.2+, matching its existing use of Environment.ProcessPath; the
administrator disk writer remains Windows PowerShell 5.1 compatible.
Neither runtime checks nor boot preparation have run on hardware in this
PC session. Seven audio candidate packaging tests also passed again.

## Physical Audio Deployment Completed

Audio Apply ran from 11:22:02 to 11:32:31 on September 10, 2026.
The matching attempt receipt was recorded at 11:26:44 after all prewrite
gates passed. The final receipt and transcript confirm:

- Only TF2 p3 was written; complete 2147483648-byte vendor readback equals
  `9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`.
- GPT head/tail and ANBOOT match the fresh deployment backup.
- Complete live system hash remains
  `199c03bf5b46a81e26aab133d8310ae576690c99c926b1835d5f3e8ac3115faa`.
- No data/ROMS or TF1 writes were requested. Data/ROMS were not fully hashed.
- No reboot, FAT repair or startup preparation was requested.
- Administrator process exited 0; all raw disk/volume handles are closed.

Evidence: `out/tf2-audio-backup-20260910-110849/Apply-result.json`,
`apply-attempt.json`, the full Backup/Apply transcripts, and outer process
logs/status in `out/tf2-audio-deploy-20260910-110849/`.
The verified old vendor, ANBOOT and GPT copies remain in the backup directory.
The original candidate manifest remains an immutable pre-deployment record;
this separate Apply receipt records physical deployment.

The card remains in the PC reader, not ejected. The user should keep it there
until the separate p1 repair scope has been reviewed and authorized.
Persistent sound after reboot and QQ Music playback are NOT yet accepted.

## Next Hardware Acceptance Gate

After verified vendor deployment, retain the unresolved p1 FAT findings as
a separate boot-readiness issue. Do not use a historical p1 or p4 recovery
image: both partitions have been used by Android since the previous repair.
Any repair requires a current backup, reviewed changes and separately
authorized write scope. Before Android boot, check the live p1 filesystem
and p4 journal/clean state without automatic repair. Use only the explicit
`audio` profile for subsequent guarded startup.

After startup, run the Audio runtime checker, confirm no temporary mixer
bind mount, verify service stability and check actual QQ Music playback with
media volume initially low. A heard test tone from the previous boot is not
proof of persistent startup or application playback. Headphones, HDMI,
capture, cold boot, suspend and the formal soak remain unaccepted.

## Runtime Probe Evidence

Directory: `out/rgsp-audio-20260910/`.

- `01-framework/rgsp_serial_exec_20260910_085614_115200.log`
- `02-hal/rgsp_serial_exec_20260910_085652_115200.log`
- `03-route-init/rgsp_serial_exec_20260910_085730_115200.log`
- `04-permissions/rgsp_serial_exec_20260910_085801_115200.log`
- `08-permission-apply/rgsp_serial_exec_20260910_090517_115200.log`
- `10-mixer-inventory/rgsp_serial_exec_20260910_090720_115200.log`
- `20-tone-probe/rgsp_serial_exec_20260910_091906_115200.log`
- `21-tone-after/rgsp_serial_exec_20260910_091932_115200.log`
- `22-trial-rollback/rgsp_serial_exec_20260910_092101_115200.log`

The first command's exit status 1 came from missing tiny-tool glob paths;
its preceding framework and ALSA output is retained. Later commands include
best-effort reads, so individual diagnostics are assessed from log content,
not only the final command exit code.
