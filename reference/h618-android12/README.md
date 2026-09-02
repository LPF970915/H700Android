# H618 Android 12 Reference Boundary

H618 is a backup comparison source only. It is not part of the H700 Android 10
mainline because its Android 12 generation, newer HAL contracts, memory target
and graphics/storage assumptions do not match the 1 GiB RGSP Linux 4.9 target.

The retained searchable set is located at:

`work/h700-source-analysis/h618/selected/`

It contains:

- `device/softwinner/apollo` and common Android 12 product configuration;
- 2 GiB Go overlays, init, fstab, audio and media configuration;
- the extracted 100 MiB `vendor_a` filesystem, including HAL services, VINTF,
  init rc, libraries and build properties;
- selected system build/VINTF metadata;
- a SHA-256 manifest generated before removal of the original large archives.

The compact official Android 12 image archive and its vendor MD5 file are kept
under `H700_Android_Example`. Full Android 12 source parts, their merged copy,
raw image and super extraction intermediates were removed after verification.
