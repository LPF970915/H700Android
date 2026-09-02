# fix58 H616 Audio Analysis

Date: 2026-09-02

## Determined failure

The fix57 `audioserver` tombstones (`tombstone_32`, `_34`, `_36`, `_38`) all report:

```text
signal 11 (SIGSEGV), fault addr 0x0
#00 libaudiohal@6.0.so android::V6_0::DevicesFactoryHalHidl::onFirstRef()+592
#01 libaudiohal@6.0.so android::V6_0::DevicesFactoryHalHybrid(...)
#02 libaudiohal@6.0.so createIDevicesFactory
```

The crash occurs while AudioFlinger creates the devices factory, before the vendor primary HAL opens an ALSA PCM device. This rules out a first-order mixer-path or PCM-open crash.

## Version/ABI mismatch

The current fix57 system contains:

- 64-bit Android 11 `audioserver` and `libaudiohal@6.0.so`.
- Active VINTF manifest entries for `android.hardware.audio@6.0` and `audio.effect@6.0`.
- A 32-bit `/vendor/bin/hw/android.hardware.audio.service` whose strings expose the H616-era `@5.0` factory as well as compatibility symbols, while its original rc advertises only `@2.0`/`@4.0`.
- Only RK3326-named primary audio binaries in the active vendor tree (`audio.primary.rk3326.so`), while the H616 reference image ships `audio.primary.cupid.so`.

This leaves the framework requesting an `@6.0` factory that is not reliably registered by the legacy service, producing the null dereference in `DevicesFactoryHalHidl::onFirstRef`.

## Hardware evidence

The H700 projector cold-boot log reports:

```text
sunxi-codec-machine ... mapping ok
ALSA device list:
  #0: audiocodec
  #1: sndspdif
  #2: sndahub
  #3: sndhdmi
  #4: snddaudio0
```

Its H700 DTS uses the same internal codec/AHUB topology as H616 for the primary path. The H700-only external capture path (`ac107.3-0036`) repeatedly fails registration, but it is not needed for boot audio.

## Candidate fix

`tools/build_fix58_h616_audio_candidate.ps1` creates a candidate by preserving fix57 display/GPU files and replacing only audio with the H616 Android 10 stack:

- H616 `android.hardware.audio@2.0-service` and `android.hardware.audio@5.0-impl`.
- H616 `audio.primary.cupid.so` and effect implementation.
- H616 audio policy, platform-info, mixer-path and volume files.
- Manifest audio HAL entries changed from `@6.0` to `@5.0`.
- A delete list for the stale RK3326 audio service rc.

H618 Android 12 files are intentionally excluded. No device write is performed by the build script.

## Expected next test

If the candidate starts `audioserver` without the `libaudiohal@6.0` null dereference, AudioService should complete its native strategy query. Only then should PCM/mixer behavior be debugged; the expected primary card is `audiocodec`, device 0, 48 kHz stereo as specified by H616 `audio_platform_info.xml`.

## Deployment status

Fix58 was installed to TF2 system from the Linux fallback environment on 2026-09-02. Before the write, the script verified the Linux root device, both TF card CIDs, and the original TF1 boot and environment hashes. The system filesystem passed read-only `e2fsck` both before and after installation.

The installed audio service, `@5.0` implementations, primary HAL aliases, manifest, policy, platform, mixer, effects, and init rc all passed a read-only SHA-256 verification against the candidate payload. The obsolete disabled RK3326 service rc was removed. No H618 Android 12 audio binary was installed.

Cold-boot validation is still pending. The decisive checks are whether `audioserver` survives factory creation, whether the H616 service registers `@5.0::IDevicesFactory/default`, and whether the primary HAL proceeds to card `audiocodec`, device 0.
