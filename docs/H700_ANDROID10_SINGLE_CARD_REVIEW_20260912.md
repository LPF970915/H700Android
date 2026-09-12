# H700 Android 10 Single-Card Review

Date: September 12, 2026, Asia/Shanghai.

## Verdict

NO-GO for physical boot testing.

The current 64GB card has a verified write/readback for the main prefix,
Android boot partition, system, vendor, data, and ROMS metadata. It is not a
fully qualified release or test card because the backup GPT tail cannot be
read through the current USB reader, and the staged system/vendor inputs are
older than the latest documented Fix72/Audio candidates.

## Real-Machine Boot Evidence

The UTRA serial link was restored on COM4 at 115200 8N1. The machine reached
`root@ANBERNIC:~#` and reported:

- Linux root: `/dev/mmcblk0p5`, the TF1 card.
- Linux boot partition: `/dev/mmcblk0p4`.
- Android test card: `/dev/mmcblk1`, mounted only as `/mnt/sdcard`.
- Android test-card layout on the running machine: p1 ANBOOT, p2 system,
  p3 vendor, p4 data, p5 ROMS.
- The running machine was therefore a TF1 Linux boot, not an independent
  Android boot from the test card.

The kernel command line retained the vendor Linux layout:
`root=/dev/mmcblk0p5` and partitions `special`, `boot-resource`, `env`,
`boot`, `rootfs`, `appfs`, `UDISK`, `primary`.

## Card Verification

Target identity remained Disk 3, USB `Generic MassStorageClass`, serial
`000000001539`, size `62239277056` bytes.

The written GPT was re-parsed by Windows as the expected eight partitions:

1. special, 36 MiB to 100 MiB
2. boot-resource, 100 MiB to 132 MiB
3. env, 132 MiB to 148 MiB
4. boot, 148 MiB to 212 MiB
5. system, 212 MiB to 8.21 GiB
6. vendor
7. data
8. ROMS

The administrator readback of the first 212 MiB matched
`prefix-212m.bin` exactly. Independent subrange checks also matched:

- Boot package at LBA 32800: `957929afa2879e18ff758d93eafa98879b21aec70dedcb731d7862a2c20f075c`
- Original env head: `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`
- Android p4 boot: `4651678a060e03692b84de3076b44ad53326ac41662d0da03b20832864f27c74`

The complete writer run at
`out/rgsp-single-card-v2-20260911/write-20260912-011750-833/` verified the
main ranges:

- prefix: `bcca9ba02e60cb34843d88fbe69be77ce69d309e0d1096421e12829a4b5743f5`
- system: `afc6072bad74d55c7be4f633d831de30168491b065b5ac538faf9b19a6fea919`
- vendor: `3196a10326d139c235f3e45617ab6bd29be7494e5b31458dbd8187763bc1687b`
- data: `54a3bc84fb6701b0caee5409a1b5ee222e81d9d759f9c8687e06bbf40827c1a1`
- ROMS metadata: `2cc806d01558eafe2cb81a0e54ad8a56e676e932381ffaf9541f1b6f64c1cd6e`

The final 1536-byte GPT tail could not be read. Even a separate 512-byte
read at LBA 121561085 returned the Windows error “drive cannot find the
requested sector”. This leaves the backup GPT unverified.

## Input Version Mismatch

The current card used:

- system `afc6072...`, from `out/rgsp-single-card-20260911`
- vendor `3196a103...`, from `out/rgsp-single-card-20260911`

The latest documented candidates are:

- Fix72 system `199c03bf...`
- Audio vendor `9d0c8d4a...`

The current card must not be described as the latest Fix72/Audio candidate.
A new card should be rebuilt from the latest inputs only after the complete
boot layout and card-tail strategy are resolved.

## Release Gates Still Open

1. Read and verify the backup GPT using a reader or Linux host that can address
   the final sectors.
2. Rebuild with the latest verified system/vendor inputs, then repeat all
   hashes and filesystem checks.
3. Confirm the device's U-Boot automatic main-slot selection with UART during
   a cold boot and with both original work cards removed.
4. Confirm Android reaches first-stage init, mounts p5/p6/p7, and records a
   persistent boot log before calling the card an independent Android card.

Do not format or test the current card in the handheld until these gates pass.
