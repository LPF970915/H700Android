# H700 v5f ROMSPublic Baseline

Overview: `docs/H700_V5F_ROMS_BASELINE.md`.
Git tag: `baseline/h700-v5f-roms`.
Authoritative status: `image-manifest.json`.
The full-image gate passed: `OFFLINE_VERIFIED_READY_FOR_FLASH`.
Checksum: `image.sha256`.

## Image

- Local file: `out/H700_Android_SingleCard_v5f_ROMSPublic.img`.
- Size: 32,434,554,368 bytes, about 30.2 GiB.
- Card: 64 GB or larger supported card.
- Prior output `out/H700_Android_SingleCard_v5e_AT4KDefault.img` is preserved.
- Complete images remain local and are not committed to Git.
- Physical first-boot/reboot acceptance remains pending.

## Reproduction

Use the existing locally prepared Android tree and signing/donor inputs.
Do not deploy the new whole-card fstab without the protected vold backend.

1. Run `tools/prepare_rgsp_roms.py --source
   /home/lpf/h700-android10/android` in WSL to apply hash-pinned native and
   framework patches and synchronize the matching product files.
2. Run `tools/build_h700_low_pressure.ps1 -Targets systemimage,vendorimage
   -Execute` in PowerShell. It retains the established resource limits.
3. Convert the newly built sparse system/vendor images with the Android
   host `simg2img` tool to new raw 8 GiB / 2 GiB files.
4. Run the packaging command below, using the retained hash-pinned v5d
   image only as the hardware/blank-data source.
5. Run `tools/verify_rgsp_compact_image.py OUTPUT.img` as WSL root. Only an
   `OFFLINE_VERIFIED_READY_FOR_FLASH` manifest is an offline-passed image.
   Never flash a `.partial` or failed candidate.

```sh
python3 tools/build_rgsp_compact_image.py \
  --system /home/lpf/rgsp-grow-build/system.raw.v5f.img \
  --vendor /home/lpf/rgsp-grow-build/vendor.raw.v5f.img \
  --roms-vold \
  --baseline out/H700_Android_SingleCard_v5d_BootInput.img \
  --output out/H700_Android_SingleCard_v5f_ROMSPublic.img
```

The builder requires an unused output path. Grow build/runtime defaults are
the existing verified `/home/lpf/rgsp-grow-build` and
`/home/lpf/rgsp-grow-runtime/runtime`.

Full-image flashing overwrites card files. Back up ROMS and other needed
data first; the factory image deliberately contains blank userdata and no
live device credentials.
