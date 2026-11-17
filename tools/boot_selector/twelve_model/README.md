# Twelve-model boot routing candidate

This directory extends the existing manual selector. The user-supplied
`../reference_model.py` catalog remains the source of model names, form factors,
stick counts and lid flags. No route consults RAM, serial numbers or stick
presence to decide whether Android may start.

`models.py` assigns explicit electrical profile indexes:

| Index | Model | Native panel | Logical screen | Lid | Sticks |
| --- | --- | --- | --- | --- | --- |
| 0 | 34XX SP / original RGSP | 720×480 | 720×480 | yes | 2 / 0 |
| 1 | 35XX H | 640×480 | 640×480 | no | 2 |
| 2 | 34XX | 720×480 | 720×480 | no | 0 |
| 3 | CubeXX | 720×720 | 720×720 | no | 2 |
| 4 | 35XX Plus / 35XX+ 2025 | 640×480 | 640×480 | no | 0 |
| 5 | 28XX | 480×640 | 640×480 | no | 0 |
| 6 | 40XX H | 640×480 | 640×480 | no | 2 |
| 7 | 40XX V | 640×480 | 640×480 | no | 1 |
| 8 | 35XX SP | 640×480 | 640×480 | yes | 0 |
| 9 | 35XX Pro | 640×480 | 640×480 | no | 2 |

2025 currently shares the pinned Plus reference as a documented candidate
assumption; no independent 2025 hardware acceptance is implied. The 28XX uses a
90 degree menu surface map and carries native/logical/rotation metadata to the
Android integration. Its physical orientation still needs hardware validation.

`selector_init.sh` permits all twelve canonical models and validates the
catalog-derived lid flag. Defaults, one-time selection, saved selection and the
power-on volume-down reselect route remain the same. The native menu receives
the full model list; it no longer rejects nine catalog entries at Start.

`early_profile_bridge.S/.py` performs the model lookup before first display.
All twelve names and all ten numeric timing rows fit the original bounded
early-hook cave. Malformed records retain the original 720 fallback; an absent
record opens the initial 35XX H 640 menu. Only the route changes when volume
down is held. The builder can accept a parent-supplied complete dispatcher via
an explicit path plus exact SHA256; a twelve-model display dispatcher is still
required for complete image integration.

`../../release/h700_manual_selector_twelve.py` writes a simple-parser boot
environment for every model. It preserves the Test7 control-FDT handoff fix,
`fdt addr ${fdtcontroladdr}`, and emits model, lid, stick count, form factor,
native size, logical size, rotation and panel profile in the kernel command
line.

`selector.c` renders the same 640×480 logical menu onto a 480×640 framebuffer
for 28XX. Pixel mapping respects the physical stride, offsets, bitfields and
visible bounds. Other display paths keep the original drawing coordinates.
The build includes host and actual AArch64 selftests with asymmetric rotation
marks and untouched-padding checks.

The final `selector_loading.c` and `build_native_loading.py` retain that
renderer and clear the menu after an accepted Start request. They leave
“加载中，请稍后” visible while init prepares userdata and Android starts.
`selector_init_loading.sh` also invokes framebuffer-only `--loading-only` after
validating saved and one-time routes, including the boot after changing the
model. This mode rejects input/result arguments and exits immediately after
painting; display failures continue to Android. The normal Android logo/UI
replaces the frame when it draws. The message does not prove Android has
finished booting. The physical A/B mapping remains unchanged. Earlier v4
progress source and receipts are retained separately.

The early timing table and environment include `lcd_frm`: 28XX uses zero and
the other pinned electrical profiles use one. There are thirteen u32 cells
per early timing row, including the explicit profile index.

This is an isolated candidate. Components and generated environment tests do
not establish physical display, joystick direction, lid or full-family
acceptance. The parent must integrate the display programs, input loader and
model-aware lid service, then verify the actual packaged bytes.

The November 17 recovery candidate uses separate `selector_rescue.c`,
`selector_init_rescue.sh`, `boot_state_preview.c` and
`early_profile_bridge_rescue.S/.py`. Earlier source and receipts stay frozen.
Volume Down advances the menu trial between 35XX H 640x480, 34XX SP 720x480,
and CubeXX 720x720; Volume Up reverses it. These three representatives follow
the user's explicit menu requirement. The twelve normal model selections
still retain ten distinct electrical profiles. A common logical resolution
does not establish physical compatibility with a trial representative.

A complete fresh volume press and release requests only `preview`: it writes
`roc_next_start=2` and the trial model, retaining `roc_saved_model`. Early boot
initializes that trial panel and returns to `selector`, never `start_once`.
The request stays pending until a normal model confirmation, so powering off
at the menu returns to the same trial on the next boot. `save`, `once`, or
`clear-next` then consumes it. Startup-held volume controls, kernel repeats,
dropped-event recovery and simultaneous volume buttons cannot request trials.
A missing or invalid framebuffer allows volume trials while rejecting ordinary
Start confirmation. The program cannot detect whether an otherwise valid
framebuffer is physically visible on a mismatched panel.
