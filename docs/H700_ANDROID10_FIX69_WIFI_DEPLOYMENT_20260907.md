# Fix69 Wi-Fi Deployment Preparation

Date: 2026-09-07. Device: RGSP/H700, no analog sticks.

## Status

The offline package, TF2 backups, physical write and full readback are
complete. The writer exited 0 at 2026-09-07 10:55:16 +08:00 with
`TF2_WRITE_READBACK_OK`. Both physical partition hashes match the final
image hashes below; GPT and ANBOOT match the reviewed protected snapshots.
This does not yet claim a successful Android boot or Wi-Fi connection.

This is the existing Fix67 bring-up configuration plus the RGSP Wi-Fi
changes, not a production image, clean-data qualification, or proof of
standalone TF2 cold boot. AT4K remains an ordinary data-side application.

## Why The Original Preflight Was Not Written Directly

File-level comparison against the actual TF2 exposed missing deployment
repairs in the raw build output: the Mali kernel module, graphics init rc,
framework restart trigger, fixed LCD configuration, bounded log capture,
and disabled Homlet displayservice autostart.

`tools/prepare_rgsp_wifi_deployment.py` applies the verified Fix67 repairs
to separate regular image copies. It verifies the preflight hashes and the
tracked Fix67 payload manifest before making changes. It neither mounts
physical card partitions nor formats Android data.

The resulting package is:

```text
out/rgsp-fix69-wifi-deployment/
  system.raw.img
  vendor.raw.img
  CONTENT_CHECKS.json
  DEPLOYMENT_MANIFEST.json
  system.raw.img.fsck.txt
  vendor.raw.img.fsck.txt
  AT4K-launcher.apk
  ramdisk-a10-handoff-fix67.gz
```

The proprietary APK, modules and image files stay local, outside Git.

Both final filesystems passed `e2fsck -fn` with exit code 0. Read-only
comparison of file contents, modes, owners and symlink targets found:

- System: only `default.prop` differs from the actual Fix67 partition.
  The added HWUI/display values match values already present in
  `/system/build.prop`; no system binary or calibrated keylayout differs.
- Vendor: differences are the Wi-Fi module, firmware, init loading rule,
  recompiled `libwifi-hal.so`, firmware search directories, and directory
  ownership. The original GPU EGL/HWC and LCD configuration are retained.
- This comparison does not certify SELinux xattrs, production security or
  runtime behavior. The existing permissive bring-up boundary remains.

Final image SHA-256:

```text
system.raw.img
d5b55d09ac9b885e925315d439dad512398e6e6081af090366c167803ce66f7b

vendor.raw.img
fd8ade095dddc1a5f2c1b7f4f4305bb4fd8d09a3dd9420658096c38b0ac41f0f
```

## Card Identity And Backup

The inserted card was identified as Windows PhysicalDrive3, USB/GPT,
125069950976 bytes. All five partition offsets, sizes and UUIDs match the
previous UART record. The reader does not expose the SD CID; identity is
corroborated by GPT UUIDs, known ANBOOT contents and the original Linux boot
image SHA-256, not by claiming a new USB-side CID read.

The Linux recovery image hash is
`d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`.
The last handoff log records its successful restoration, and no
`RGSP_ANDROID_TRY.ONCE` request was left pending.

Verified local backups:

```text
out/tf2-deploy-20260907/
  backup.json
  gpt-head.bin
  anboot.img
  system.before.img
  vendor.before.img
  gpt-tail.bin
```

Old system SHA-256:
`3ccd05f9eba560665c8c7125dcd9edfaa63ad566248b6c77076a0297ca1eb67d`.
Old vendor SHA-256:
`80bdab69f37883e1e6d86e82b0d84323c94d884a45d3a976cd8e45edc3a504d8`.

`tools/invoke_rgsp_tf2_guarded_deploy.ps1` checks disk and all partition
identities, verifies backup/source/current-range hashes, locks p1/p2/p3 volumes,
writes only p2/p3, and verifies full readback. GPT and ANBOOT hashes are
checked again after writing. It never writes TF1, Android data p4, or ROM p5.

Negative tests against the host SATA and NVMe system disks both stopped at
the identity gate, before opening either raw disk. The Python deployment
helper tests passed 4/4.

### ANBOOT Access-Date Change

The first write attempt stopped at the ANBOOT hash gate before any image
bytes were written. Comparing the original and locked-volume snapshots
found zero file-content or directory differences and exactly one changed
byte at ANBOOT offset 8649426. This is offset 18 of the FAT directory entry
at 8649408 (`ANBERN~1KL`), the last-access date of `ANBERNIC-keys.kl`:
2026-09-06 became 2026-09-07 after reading it through Windows.

The original backup was retained. A second snapshot, taken with ANBOOT
locked and flushed, is stored at `out/tf2-deploy-20260907-boot-locked/`.
Its ANBOOT SHA-256 is
`ef0ac748733c45383aa4d3adeea875770dd7ad0e0673a52b95d5224e696c9bd1`.
Both GPT hashes stayed identical. The writer now locks ANBOOT as well as
system/vendor, and the retried write uses this explicitly reviewed boot
snapshot while still checking the original system/vendor backup hashes.
It does not silently accept an arbitrary changed ANBOOT.

## Next Hardware Gate

1. Write/readback is complete and all writer handles are closed. Safely
   remove the USB card reader before moving the card.
2. Reinsert TF2 into the powered-off RGSP and boot original Linux.
3. Recheck both live CIDs, TF1 boot/env hashes and TF2 contents over COM4.
4. Use the protected Fix67 one-shot handoff, not the original unpatched
   preflight test boot image. Preserve Linux recovery and existing data.
5. Verify Android boot completion, GPU identity, key input, loaded `8821cs`,
   SDIO probe, `wlan0`, Wi-Fi HAL, Settings switch and scanning.
6. Test authentication, DHCP, DNS, HTTPS and reconnect with user-supplied
   network credentials. Do not store credentials in Git.
7. Regress AT4K DPAD focus, A confirm, B return and network settings before
   changing default HOME.

Persistent TF2 boot selection remains separate work. This session does not
write U-Boot, its environment or TF1 boot, and does not establish that the
device can cold boot from TF2 without TF1.
