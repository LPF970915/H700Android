# Fix72 Reproduction Lock

Date: 2026-09-08. Scope: original no-stick RGSP candidate, not RGSPLauncher.

## Frozen Inputs

The candidate's packaging commit is
`e3566a9cfbf0d86dbb576631497adc6ea5ee94ce`.
An independently retained `git archive` contains that commit's RGSP overlay,
LeanbackIME patch, build/staging/packaging tools, Fix67 hash list and provenance
documents:

- File: `out/rgsp-fix72-source-e3566a9.tar`
- Bytes: 4085760
- SHA-256: `b3fef1982054dc8448a337a6f9b8e6588233750359fdbce816e8979199626fa0`

This archive is source/provenance material, not a device installer or a
complete Android source-tree snapshot. Do not overwrite the current working
tree or invoke historical device-writing helpers to reproduce it.

The current `out/rgsp-fix72-build-inputs.json` includes RGSPLauncher changes.
It is not the original candidate's build lock. The packaging commit also
does not prove that every untracked change in the original Android build
tree was captured.

Retained binary input sets:

- `out/rgsp-fix72-preflight/DEPLOYMENT_MANIFEST.json`: sparse build inputs.
- `out/h700-android10-b2/`: pinned Fix67 deployment payload, checked against
  `docs/baselines/fix67-payload.sha256`.
- `out/rgsp-fix70-wifi-home/`: the two pinned Fix70 Wi-Fi files.
- `out/rgsp-fix72-wifi-profile/DEPLOYMENT_MANIFEST.json`: fixed candidate.
- `out/rgsp-fix72-wifi-profile/CONTENT_CHECKS.json`: 17 deployed components.

The official H616 source archives and verified identities are recorded in
`docs/H616_ANDROID10_PROVENANCE_20260902.md`. LeanbackIME's pinned revision
and local patch contract are in the archived preparation script.

## Reproduction Boundary

The frozen raw candidate can be redeployed using its manifest and the
current guarded writer. This has been verified by full physical readback.
Rebuilding the known boot from the pinned base image and handoff ramdisk
also reproduces its exact SHA-256 in the host test and device preflight.

Repackaging requires first restoring the pruned raw preflight images from
the retained sparse files, then checking their original sizes and hashes.
Use a NEW output directory with `prepare_rgsp_wifi_deployment.py`; its
existing-output refusal must remain enabled. Do not target the frozen
candidate directory as a new packaging output.

The ext4 packaging procedure writes filesystem metadata and records a
generation timestamp. Its second run has not been verified as byte-for-byte
identical. Compare component content and filesystem structure as well as
recording each complete image hash; do not promise equal raw hashes.

Two clean Android builds have NOT been completed. Before that qualification:

1. Inventory non-overlay changes and toolchain inputs in the Android tree.
2. Preserve existing work and prepare an isolated, reviewed source baseline.
3. Check disk/RAM headroom. All builds must use
   `tools/build_h700_low_pressure.ps1 -Execute`, with the existing one-core,
   `-j1`, 6 GiB memory and 512 MiB swap limits unchanged.
4. Build and package into separate outputs, compare critical component
   inventories, and explicitly report nondeterministic differences.

No new Android build or large raw-image copy was started at this checkpoint.

## Later Codec Candidate

The statement above describes the initial freeze checkpoint. On September 8
a vendor-only incremental build completed at 13:01:38 CST, followed by a
separate 2 GiB local vendor copy with only three reviewed codec XML additions.
Neither changes the original frozen package or establishes two clean builds.

Inputs and results:

- `out/rgsp-fix72-codec-probe-20260908/`: trial payload, screenshots,
  current build-input snapshot, product diff, sparse/raw build and fsck log.
- `out/rgsp-fix72-codec-candidate-20260908/`: narrow offline candidate,
  manifest, read-only fsck results, independent content comparison and
  executed recipe/dependency snapshots.
- Candidate vendor SHA-256:
  `1e1c90ffdc6fc08e7e40d333d3fab4ea065c19a34df38b4a0889bcc83a8dc891`.

To reproduce the semantic candidate with retained pinned binary inputs,
run the archived `prepare-executed.py` using WSL root and the existing
one-core/low-priority settings, with `--workspace /mnt/d/Works/H700Android`,
`--output` pointing to a NEW path inside `out`, then explicit `--prepare`.
Without `--prepare`, it only validates paths and input hashes. It refuses
an existing output and any copy that would cross the 120 GiB free-space
floor. Its two archived Python dependencies must remain beside it.
No Android compilation or physical-device write occurs in this recipe.

Compare the manifest's three file additions and all preserved file metadata,
not a promised byte-identical ext4 hash: new inode timestamps/allocation and
manifest generation time can differ. Keep the recorded full image hash for
this specific candidate. Its `/vendor/etc` placement still needs persistent
hardware qualification; the successful RAM trial used `/vendor/odm/etc`.
The candidate is deliberately not labeled deployment-ready and cannot be
passed directly to the existing two-partition writer or boot-only helper.

## Recovery

The verified physical pre-write recovery set remains at
`out/tf2-fix72-deploy-20260907-current-v2/`. Its receipts distinguish the
successful system/vendor flash from the later data fsck scope violation.
The original raw data backup remains the pre-repair version; it is not a
backup of the current clean filesystem. Never replay repair or restore it
automatically, and do not assume data-preservation acceptance until apps
and settings have been tested on the device.
