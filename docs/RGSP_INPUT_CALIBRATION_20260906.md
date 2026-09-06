# RGSP Physical Input Calibration

Date: 2026-09-06. Status: short-press profile verified; basic RGSP
keylayout installed for bring-up, not a final multi-model mapping.

Latest check at 23:22 CST: the live Fix67 keylayout SHA-256 matches the
repository's current A-to-ENTER profile:
`99b729a799e47db82a389527e4cc232e186d4a1c431f119326fb093a9def9056`.
Basic short-press calibration is complete; subsequent development should
test the TV frontend and Settings rather than repeat this capture sequence.
Historical references below to missing WifiService describe earlier boots:
the Fix67 runtime now publishes that service, but has no working wlan0 yet.

## Model Scope

- This session applies only to the user's RGSP, which has no analog sticks.
- H700 is a SoC family, not a universal physical-button profile. Other models
  must have their own verified profiles and calibration records.
- Do not identify a physical model solely from an input-device name, shared
  VID/PID, or advertised axis capabilities. The current driver advertises
  additional axes even though this RGSP has no physical analog sticks.
- The future first-boot flow should select or calibrate the hardware profile
  before entering the normal launcher. It must support recalibration and
  recovery. Models with real sticks also need center/range/dead-zone tests.
- Never promote a partially observed profile into the active system mapping.

## Observed Buttons

| Physical control | Device | Event | Press | Release | Evidence |
| --- | --- | --- | --- | --- | --- |
| D-pad Up | ANBERNIC-keys | EV_ABS (0x03), ABS_HAT0Y (0x11) | -1 (0xffffffff) | 0 | Three complete cycles |
| D-pad Down | ANBERNIC-keys | EV_ABS (0x03), ABS_HAT0Y (0x11) | +1 (0x00000001) | 0 | Three complete cycles |
| D-pad Left | ANBERNIC-keys | EV_ABS (0x03), ABS_HAT0X (0x10) | -1 (0xffffffff) | 0 | Three complete cycles |
| D-pad Right | ANBERNIC-keys | EV_ABS (0x03), ABS_HAT0X (0x10) | +1 (0x00000001) | 0 | Three complete cycles |
| Physical A | ANBERNIC-keys | EV_KEY (0x01), code 0x130 | 1 | 0 | Three complete cycles |
| Physical B | ANBERNIC-keys | EV_KEY (0x01), code 0x131 | 1 | 0 | Three complete cycles |
| Physical X | ANBERNIC-keys | EV_KEY (0x01), code 0x133 | 1 | 0 | Three complete cycles; differs from historical table |
| Physical Y | ANBERNIC-keys | EV_KEY (0x01), code 0x132 | 1 | 0 | Three complete cycles; cross-check confirms historical X/Y discrepancy |
| Physical L1 | ANBERNIC-keys | EV_KEY (0x01), code 0x134 | 1 | 0 | Three complete cycles |
| Physical R1 | ANBERNIC-keys | EV_KEY (0x01), code 0x135 | 1 | 0 | Three complete cycles |
| Physical L2 | ANBERNIC-keys | EV_KEY (0x01), code 0x13a | 1 | 0 | Three complete cycles bracketed by known L1 presses |
| Physical R2 | ANBERNIC-keys | EV_KEY (0x01), code 0x13b | 1 | 0 | Three complete cycles bracketed by known R1 presses |
| Physical Select | ANBERNIC-keys | EV_KEY (0x01), code 0x136 | 1 | 0 | Three complete cycles; earlier separate 0x131 cycle also recorded |
| Physical Start | ANBERNIC-keys | EV_KEY (0x01), code 0x137 | 1 | 0 | Three complete cycles |
| Physical Menu (short press) | ANBERNIC-keys | EV_KEY (0x01), 0x138 followed by 0x162 | 1 for each code | 0 for each code | Three identical two-code sequences; not a simple one-code mapping |
| Physical Menu (observed 3.11-3.27 s hold) | ANBERNIC-keys | EV_KEY (0x01), code 0x138 only | 1 | 0 | Three complete cycles; no 0x162 or raw repeats |
| Physical Volume Down | ANBERNIC-keys | EV_KEY (0x01), code 0x72 | 1 | 0 | Three complete cycles |
| Physical Volume Up | ANBERNIC-keys | EV_KEY (0x01), code 0x73 | 1 | 0 | Three complete cycles |

The Up capture contained six axis transitions and six SYN_REPORT records.
No raw events came from either auxiliary input device. Approximate hold
times were 230, 180, and 220 ms. This verifies short presses only, not
long holds, diagonals, repeats, or game/application behavior.

Capture:

```text
out/input-calibration/20260906_122721-rgsp-dpad-up.log
SHA256: 9bddec6e306c35fd0a85e0cc2393e08b0bf1483aef52e01e2c0d3dd20d7a30ba
```

The Down capture also contained six axis transitions and six SYN_REPORT
records, with no raw events from auxiliary devices. Approximate hold times
were 210, 240, and 270 ms.

```text
out/input-calibration/20260906_122952-rgsp-dpad-down.log
SHA256: 53f6a02c98c1452866dba048b772a760bf5052633bfa53096af13b7353c54d6e
```

The Left capture contained six axis transitions and six SYN_REPORT records,
with no raw events from auxiliary devices. Approximate hold times were
270, 180, and 230 ms.

```text
out/input-calibration/20260906_123148-rgsp-dpad-left.log
SHA256: 384d5d045e1b872f5bc7cd550ca6062bed6d359916799f1f4aa82ed919978342
```

The Right capture contained six axis transitions and six SYN_REPORT records,
with no raw events from auxiliary devices. Approximate hold times were
200, 210, and 210 ms. All four single-direction short-press observations
are now recorded; diagonals and hold/repeat behavior remain untested.

```text
out/input-calibration/20260906_123417-rgsp-dpad-right.log
SHA256: 79278aae4b71b3621bb8532ead65d3e814bdc11d69a799291ae8bbcd9ecc6454
```

The physical A capture contained six key transitions and six SYN_REPORT
records, with no raw events from auxiliary devices and no repeat-value
events. Approximate hold times were 160, 190, and 210 ms. The physical
label is user-observed; this does not yet assign an Android navigation action.

```text
out/input-calibration/20260906_123701-rgsp-button-a.log
SHA256: 8170ba57a612f1a7c35bb84bce477cd6e4f3e85530e69f988d26fccbeaf79cec
```

The physical B capture contained six key transitions and six SYN_REPORT
records, with no raw events from auxiliary devices and no repeat-value
events. Approximate hold times were 220, 220, and 240 ms.

```text
out/input-calibration/20260906_124008-rgsp-button-b.log
SHA256: 27653c2f66fc2134d8e85d437a082aefd8cfea1d690bb0aef25fe9da4498fbfc
```

The physical X capture contained six key transitions and six SYN_REPORT
records, with no raw events from auxiliary devices and no repeat-value
events. Approximate hold times were 210, 220, and 270 ms.

The observed code is 0x133, whereas the historical hardware baseline lists
X as 0x132 and Y as 0x133. Preserve this discrepancy explicitly. The current
RGSP profile must follow verified physical observations, not the old table.
The physical Y cross-check below confirms the reversed physical labels
relative to that table. No active mapping has been deployed.

```text
out/input-calibration/20260906_124217-rgsp-button-x.log
SHA256: 17b2daf2cb45a60ec3c0d6414da194ee8f3c561d2036815b5339f26e6b84d0f9
```

The physical Y capture contained six key transitions and six SYN_REPORT
records, with no raw events from auxiliary devices and no repeat-value
events. Approximate hold times were 150, 170, and 150 ms.
The current RGSP observations are A=0x130, B=0x131, X=0x133, Y=0x132.
These are raw physical-label observations, not a family-wide H700 mapping.

```text
out/input-calibration/20260906_124423-rgsp-button-y.log
SHA256: 1d76f4789951f070ca0dfcff2a87d652cee8317f1f3dc0b0771128781ded7e95
```

The physical L1 capture contained six key transitions and six SYN_REPORT
records, with no raw events from auxiliary devices and no repeat-value
events. Approximate hold times were 120, 151, and 150 ms.

```text
out/input-calibration/20260906_124828-rgsp-button-l1.log
SHA256: f7b269760de4d7d6fd6c21f8539ee33206f7dee141ded3df994632b1d29cd672
```

The physical R1 capture contained six key transitions and six SYN_REPORT
records, with no raw events from auxiliary devices and no repeat-value
events. All three approximate hold times were 150 ms.

```text
out/input-calibration/20260906_125110-rgsp-button-r1.log
SHA256: a76e5fb7bd857daf4586ad6badffd51132b9f3cb0485e8b712db500c5bca05f5
```

## L2 Retry After Empty Capture

The 45-second physical L2 capture completed and downloaded successfully,
but contained no raw input events from any device. Its content and SHA256
match the earlier idle sample. This is not a verified L2 mapping and does
not establish a missing or broken physical control. The user confirmed
pressing L2 three times after the start prompt. The cause of this empty
capture remains undetermined; preserve it alongside the successful retry.

```text
out/input-calibration/20260906_125335-rgsp-button-l2.log
SHA256: c00b3b57267d079cda43e4821fda6cd91cf207deda809a20e7bdab64067f51e3
```

The 60-second retry again monitored all input devices and event types.
The requested sequence was L1 once, L2 three times, then L1 once, releasing
each button and leaving a gap between groups.

The observed sequence was exactly 0x134, 0x13a, 0x13a, 0x13a, 0x134, each
with a complete EV_KEY press/release and SYN_REPORT pair. All events came
from ANBERNIC-keys; there were no raw events from auxiliary devices or
repeat-value events. L2 hold times were approximately 210, 180, and 200 ms.
The known L1 bookends confirm the capture window and separate L2's events.
This establishes physical L2 as raw code 0x13a for this RGSP, without
explaining the earlier empty sample or proving long-term key reliability.

```text
out/input-calibration/20260906_125710-rgsp-l2-all-inputs-retry.log
SHA256: d89a36f1431707b03a3105106eef901e7d60860ed7ba610aebf0f42ad5aded19
```

## R2 Retries And Confirmation

The 45-second physical R2 capture completed and downloaded successfully,
but contained no raw events from any input device. Its content and SHA256
match the idle sample. No R2 code is established by this attempt, and no
hardware-fault conclusion is justified.

The retry monitored all devices for 60 seconds with requested R1 bookends:
R1 once, physical R2 three times, then R1 once, releasing each button
and leaving a gap between groups.

```text
out/input-calibration/20260906_130040-rgsp-button-r2.log
SHA256: c00b3b57267d079cda43e4821fda6cd91cf207deda809a20e7bdab64067f51e3
```

The retry also contained no raw events, including neither known R1 bookend.
Therefore it cannot isolate a fault to R2. Preserve the empty evidence and
investigate capture timing/path rather than assigning a guessed R2 code.

```text
out/input-calibration/20260906_130255-rgsp-r2-all-inputs-retry.log
SHA256: c00b3b57267d079cda43e4821fda6cd91cf207deda809a20e7bdab64067f51e3
```

At 13:06 CST, read-only checks still showed all three input devices enabled,
correct evdev permissions/labels, unchanged core PIDs, and no leftover
getevent process. This does not prove that physical events are being emitted.

An optional fallback is `tools/capture_rgsp_input_session.ps1 -Action Start`.
It arms a recording without a short time window, retains per-port metadata
in `out/input-calibration/active-COM4.json`, and applies a file-size limit.
Tell the user to press only after arming is acknowledged. When the user
reports completion, use `-Action Finish` to verify and stop the owned PID,
download with SHA256 verification, and remove the active-session metadata.
Do not start another recorder while this session is active.
This fallback has not been executed or validated on the device; the user
requested the previously successful timed L2 method instead.

The 13:08:38 timed retry finished before a start-press prompt was sent
during a context handoff. It contained no raw events and is not a valid
prompted R2 trial. Preserve it without drawing a button-fault conclusion.

```text
out/input-calibration/20260906_130838-rgsp-r2-l2-method-retry.log
SHA256: c00b3b57267d079cda43e4821fda6cd91cf207deda809a20e7bdab64067f51e3
```

The next 60-second all-input capture, started at 13:10:54, used the same
method as the successful L2 retry. After starting the recorder, the user
was prompted to press R1 once, R2 three times, then R1 once.

The observed sequence was exactly 0x135, 0x13b, 0x13b, 0x13b, 0x135,
each with a complete EV_KEY press/release and SYN_REPORT pair. All raw
events came from ANBERNIC-keys, with none from auxiliary devices and no
repeat-value events. R2 hold times were approximately 159, 150, and 150 ms.
The known R1 bookends establish the control sequence within this capture.
Physical R2 is therefore verified as raw code 0x13b for this RGSP only.
Earlier empty captures remain unexplained; no active mapping was installed.

```text
out/input-calibration/20260906_131054-rgsp-r2-l2-method-retry2.log
SHA256: 0fa6737fc54692dad9b3c7207036047e1f48cc23e8a5c784e72efedd3fb89096
```

`/dev/input/event1` is the node observed in this boot, not a permanent
device identifier for future mappings.

## Select Capture

The 60-second all-input capture started at 13:12:52. The user was prompted
to short-press physical Select three times, releasing between presses.
Three complete EV_KEY cycles of 0x136 were recorded, each approximately
150 ms long, with SYN_REPORT records and no repeat-value events.

The same log also contains one earlier complete 0x131 cycle (previously
observed for physical B), held approximately 180 ms and released about
10.87 seconds before the first 0x136 press. Its physical cause was not
confirmed by the user. Preserve it as an extra event, not a Select sample.
All raw events came from ANBERNIC-keys; none came from auxiliary devices.
The three-press sequence supports physical Select as 0x136 for this RGSP.
No Android navigation or mouse-mode action has been assigned or installed.

```text
out/input-calibration/20260906_131252-rgsp-button-select.log
SHA256: cd2e87e48997029ddb2a4643f468f12518651f195cb14e464211985c84a6c95b
```

## Start Capture

The 60-second all-input capture started at 13:14:51. The user was prompted
to short-press physical Start three times, releasing between presses.
The log contains exactly three complete EV_KEY cycles of 0x137 and their
SYN_REPORT records. Approximate hold times were 150, 180, and 160 ms.
All raw events came from ANBERNIC-keys, with no auxiliary-device events,
other key codes, or repeat-value events. This verifies physical Start as
0x137 for this RGSP only; no active mapping was installed.

```text
out/input-calibration/20260906_131451-rgsp-button-start.log
SHA256: 88fbdae07f4a7431036503918538f969ab59257f495b9ad360b1ee4b7bfbf380
```

## Menu Short-Press Capture

The 60-second all-input capture started at 13:16:42. The user was prompted
to short-press physical Menu three times, releasing between presses.
Each observed short press produced the same sequence on ANBERNIC-keys:

1. EV_KEY 0x138 value 1, then SYN_REPORT.
2. EV_KEY 0x138 value 0 and EV_KEY 0x162 value 1 in the same report.
3. Approximately 180 ms later, EV_KEY 0x162 value 0, then SYN_REPORT.

The 0x138 holds were approximately 180, 150, and 210 ms. Each 0x162
pulse lasted approximately 180 ms. All three two-code sequences were
complete, with no raw events from auxiliary devices or repeat-value events.
This is a paired short-press observation, not proof of two physical buttons
or a verified long-press policy. The producing implementation has not yet
been traced. Do not flatten Menu into a single-code assumption or bind both
codes independently to navigation actions that could execute twice.
Menu hold/release and selected chord behavior need separate calibration
before deciding how to normalize this sequence. No mapping was installed.

```text
out/input-calibration/20260906_131642-rgsp-button-menu.log
SHA256: 74621bf6d939e8a584cdbbec9b2d52664e5ec19b02fb74ae7a40844ef970a400
```

## Volume Down Capture

The 60-second all-input capture started at 13:18:55. The user was prompted
to short-press physical Volume Down three times, releasing between presses.
The log contains exactly three complete EV_KEY cycles of 0x72 and their
SYN_REPORT records. Approximate hold times were 150, 180, and 210 ms.
All raw events came from ANBERNIC-keys, with no auxiliary-device events,
other key codes, or repeat-value events. This verifies the raw physical
Volume Down code for this RGSP only, not Android volume or audio behavior.
No active mapping was installed.

```text
out/input-calibration/20260906_131855-rgsp-volume-down.log
SHA256: 9a044f2fd5e8a4572a49a26b3d0f4372e12238a4b04e1450480dfd06040a6e64
```

## Volume Up Empty Capture

The 60-second all-input capture started at 13:21:41. After the recorder
started, the user was prompted to short-press physical Volume Up three
times. The capture and SHA256-verified download completed successfully,
but the log contains no raw events from any input device. Its contents
match the earlier idle sample. No Volume Up code is established, and this
does not establish a hardware fault or the cause of the empty recording.
The user subsequently confirmed that they had not pressed the button in
this window. Treat this attempt as a confirmed no-press sample, not a
missed-input trial. This clarification applies only to this capture.

```text
out/input-calibration/20260906_132141-rgsp-volume-up.log
SHA256: c00b3b57267d079cda43e4821fda6cd91cf207deda809a20e7bdab64067f51e3
```

The initially proposed retry with Volume Down bookends was superseded by
the user's clarification and request to repeat Volume Up alone.

## Volume Up Confirmation

The 60-second all-input retry started at 13:23:42. The user was prompted
to short-press physical Volume Up three times, releasing between presses.
The log contains exactly three complete EV_KEY cycles of 0x73 and their
SYN_REPORT records. Approximate hold times were 180, 180, and 150 ms.
All raw events came from ANBERNIC-keys, with no auxiliary-device events,
other key codes, or repeat-value events. This verifies the raw physical
Volume Up code for this RGSP only, not Android volume or audio behavior.
No active mapping was installed.

```text
out/input-calibration/20260906_132342-rgsp-volume-up-retry.log
SHA256: c4b0aeba2312e9e56b90c3528d050d2d003d95565ff703cb32de3785b8a64619
```

## Menu Hold Capture

The 60-second all-input capture started at 13:27:00. The requested action
was three Menu holds of approximately 2 seconds, with complete releases
and pauses. Actual raw press-to-release durations were 3.190, 3.110, and
3.270 seconds; these are not measurements of 2-second holds despite the
capture filename.

Each hold produced only a complete EV_KEY 0x138 press/release cycle and
SYN_REPORT records on ANBERNIC-keys. No 0x162 pulses, EV_KEY value 2
repeats, other codes, or auxiliary-device raw events were recorded.
Together with the earlier 150-210 ms short presses, this establishes a
duration-dependent difference in the observed Menu sequences. It does
not establish the transition threshold, its implementation, Android-level
repeat behavior, or visible UI effects. No user report of UI effects has
yet been recorded for this trial.

Future Menu normalization must account for the short-press-only 0x162
pulse without duplicating an action already handled via 0x138. The exact
policy remains pending implementation inspection and further tests; no
active mapping was installed.

```text
out/input-calibration/20260906_132700-rgsp-menu-hold-2s.log
SHA256: a0b1a9195967dcf9d1c01ad597b7628085296bfe87c519d4312ed4fc99862949
```

## D-pad Up Hold Capture

The 60-second all-input capture started at 13:29:14. The requested action
was three D-pad Up holds of approximately 3 seconds, with full releases.
Actual axis-active durations were 1.870, 2.350, and 2.110 seconds; these
are not measurements of 3-second holds despite the capture filename.

Each cycle contained EV_ABS ABS_HAT0Y (0x11) changing to -1 (0xffffffff),
then returning to 0 on release, with SYN_REPORT records. All six axis
transitions came from ANBERNIC-keys. No intervening raw reports, other
axes, key events, or auxiliary-device events appeared in this sample.
All three releases returned the observed axis to neutral.

This verifies held-axis and release observations for these durations only.
It does not establish Android-level directional key repeat or continuous
focus movement; no framework-event or UI-repeat test was performed here.
No active mapping was installed.

```text
out/input-calibration/20260906_132914-rgsp-dpad-up-hold-3s.log
SHA256: beba55748cc03dc59e5e826feceb77c494f81a7885728095a137c16b1c3997dc
```

## D-pad Down Hold Capture

The 60-second all-input capture started at 13:31:13. The requested action
was three D-pad Down holds of approximately 3 seconds, with full releases.
Actual axis-active durations were 2.080, 2.900, and 2.870 seconds.

Each cycle contained EV_ABS ABS_HAT0Y (0x11) changing to +1, then
returning to 0 on release, with SYN_REPORT records. All six axis
transitions came from ANBERNIC-keys. No intervening raw reports, other
axes, key events, or auxiliary-device events appeared in this sample.
All three releases returned the observed axis to neutral.

This verifies held-axis and release observations for these durations only.
Android-level directional key repeat and continuous focus movement remain
untested. No active mapping was installed.

```text
out/input-calibration/20260906_133113-rgsp-dpad-down-hold-3s.log
SHA256: d420e34667228db6937f509255aa5211c094482a27d481376417a3e822d763cb
```

## D-pad Left Hold Capture

The 60-second all-input capture started at 13:33:16. The requested action
was three D-pad Left holds of approximately 3 seconds, with full releases.
Actual axis-active durations were 1.860, 2.570, and 2.250 seconds; these
are not measurements of 3-second holds despite the capture filename.

Each cycle contained EV_ABS ABS_HAT0X (0x10) changing to -1 (0xffffffff),
then returning to 0 on release, with SYN_REPORT records. All six axis
transitions came from ANBERNIC-keys. No intervening raw reports, other
axes, key events, or auxiliary-device events appeared in this sample.
All three releases returned the observed axis to neutral.

This verifies held-axis and release observations for these durations only.
Android-level directional key repeat and continuous focus movement remain
untested. No active mapping was installed.

```text
out/input-calibration/20260906_133316-rgsp-dpad-left-hold-3s.log
SHA256: ab1b758b38519ab4207d0874308ada96461e26fcd4c1d969f230b7f4570dad3f
```

## D-pad Right Hold Capture

The 60-second all-input capture started at 13:35:32. The requested action
was three D-pad Right holds of approximately 3 seconds, with full releases.
Actual axis-active durations were 1.780, 2.550, and 2.460 seconds; these
are not measurements of 3-second holds despite the capture filename.

Each cycle contained EV_ABS ABS_HAT0X (0x10) changing to +1, then
returning to 0 on release, with SYN_REPORT records. All six axis
transitions came from ANBERNIC-keys. No intervening raw reports, other
axes, key events, or auxiliary-device events appeared in this sample.
All three releases returned the observed axis to neutral.

All four single-direction holds now have observed active/neutral cycles.
This does not establish diagonal behavior, Android-level directional key
repeat, or continuous focus movement. No active mapping was installed.

```text
out/input-calibration/20260906_133532-rgsp-dpad-right-hold-3s.log
SHA256: d3d681c63eaff1893d4135d37a1f30092d920a46383056853bea8f9dd9f5ecc0
```

## A Hold Capture

The 60-second all-input capture used token 13:37:30; its UART transcript
started at 13:37:31. The requested action was three physical A holds of
approximately 3 seconds, with full releases. Actual press-to-release
durations were 3.750, 3.360, and 2.380 seconds.

The log contains exactly three complete EV_KEY 0x130 press/release
cycles and their SYN_REPORT records on ANBERNIC-keys. No EV_KEY value 2
repeats, other key codes, axis events, or auxiliary-device raw events
were recorded. All three presses have corresponding releases.

This verifies raw held-button behavior for these durations only, not
Android-level repeat, long-click handling, or application behavior.
No active mapping was installed.

```text
out/input-calibration/20260906_133730-rgsp-button-a-hold-3s.log
SHA256: 12b7cd5436826789edc11ebd465ab2cfd3f28f5f97eba57e984dd9ce309b7587
```

## B Hold Capture

The 60-second all-input capture started at 13:44:25. The requested action
was three physical B holds of approximately 3 seconds, with full releases.
Actual press-to-release durations were 2.290, 2.340, and 2.570 seconds.

The log contains exactly three complete EV_KEY 0x131 press/release
cycles and their SYN_REPORT records on ANBERNIC-keys. No EV_KEY value 2
repeats, other key codes, axis events, or auxiliary-device raw events
were recorded. All three presses have corresponding releases.

This verifies raw held-button behavior for these durations only, not
Android-level repeat, long-click handling, or application behavior.
No active mapping was installed.

```text
out/input-calibration/20260906_134425-rgsp-button-b-hold-3s.log
SHA256: c824c0781a93feba9bef9242d353a0718a85e1fd6474b39ea647d04385929c9d
```

## X Hold Capture (Incomplete)

The 60-second all-input capture used token 13:47:07; its UART transcript
started at 13:47:08. The requested action was three physical X holds of
approximately 3 seconds, with full releases.

The log contains two complete EV_KEY 0x133 press/release cycles, lasting
1.750 and 2.320 seconds, followed by a third 0x133 press without a recorded
release. Each transition has a SYN_REPORT. All raw events came from
ANBERNIC-keys, with no other codes, axes, auxiliary-device events, or
EV_KEY value 2 repeats in the captured interval.

The recording and SHA256-verified download succeeded, but the third cycle
is incomplete. It cannot establish whether release occurred after the
capture window or was absent for another reason. Do not infer a stuck or
faulty button. The user was asked to ensure X is fully released before
the next trial. The earlier short-press X mapping remains supported;
three complete long-press cycles have not yet been obtained.
No active mapping was installed.

```text
out/input-calibration/20260906_134707-rgsp-button-x-hold-3s.log
SHA256: 57bdf87f7bded8bb366887b74aa74005993700ed8d779ce31ec02c12e376d87b
```

## X Hold Retry (Complete)

The 60-second all-input retry used token 13:49:27; its UART transcript
started at 13:49:28. The user was prompted to hold physical X approximately
3 seconds three times, fully releasing after each hold. Actual
press-to-release durations were 4.690, 3.720, and 4.040 seconds.

The log contains exactly three complete EV_KEY 0x133 press/release
cycles and their SYN_REPORT records on ANBERNIC-keys. No EV_KEY value 2
repeats, other key codes, axis events, or auxiliary-device raw events
were recorded. All three presses have corresponding releases.

This completes the three-cycle X hold sample for the observed durations.
It does not explain the preceding incomplete capture or establish
Android-level repeat, long-click handling, or application behavior.
The incomplete evidence is retained. No active mapping was installed.

```text
out/input-calibration/20260906_134927-rgsp-button-x-hold-3s-retry.log
SHA256: cc8ab7ba31bae604f2dd9996a7080f9694aa29500fa125b5909b8fde656a3f09
```

## Y Hold Capture (Empty)

The 60-second all-input capture started at 13:52:48. The user was prompted
to hold physical Y approximately 3 seconds three times, with full releases.
The recording and SHA256-verified download completed, but no raw events
from any input device were captured. The contents match the idle sample.

No Y hold/release behavior is established by this attempt. Whether the
user pressed during this window has not been confirmed; do not infer a
hardware fault or assign a cause to the empty recording. The earlier
physical Y short-press observation (0x132) remains supported.
No active mapping was installed.

```text
out/input-calibration/20260906_135248-rgsp-button-y-hold-3s.log
SHA256: c00b3b57267d079cda43e4821fda6cd91cf207deda809a20e7bdab64067f51e3
```

## Remaining Sequence

The initial single-control short-press sequence is now recorded.
Menu short/long sequence differences are observed, but the threshold
remains unmeasured. All four D-pad direction holds and neutral returns
are recorded, as are physical A, B, and X holds and releases.
The first X hold trial was incomplete; the retry has three complete cycles.
The first Y hold trial contains no raw events.
Long-press, repeat, diagonal, and chord tests are intentionally deferred
to the mapping-tool phase. No active mouse-mode switch is assigned.
No active mapping was installed before the basic bring-up described below.
Next development work is outside this calibration sequence.
Power and lid-close are not part of the initial key sequence.

## Basic Mapping Bring-up

The observed short-press profile was installed only for the current RGSP
bring-up. Select remains a standard gamepad button and is not yet used as
a global mouse-mode switch.

The mapping is matched by `Vendor_0001_Product_0001_Version_0100`.
After a real protected-handoff reboot, EventHub reported:

```text
KeyLayoutFile: /system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl
```

The reboot first entered Ubuntu fallback as designed; the existing B3
handoff was then re-armed. Android subsequently booted with
`sys.boot_completed=1`, fresh core PIDs `1498/1915/2093/2266`, and the
RGSP input device enabled. Settings remains blocked by the separate
missing `wifi` framework service.

The profile is RGSP-only and must not be copied to other H700 models
without independent first-boot calibration.

The current Android runtime also showed no system-wide input freeze after
the A long-press UI state. The apparent lock was a Launcher/lock-screen
navigation gap, resolved for bring-up by mapping physical A to ENTER.

## A Unlock Bring-up

The user reported that the physical A button did not unlock the current
screen. For this bring-up profile, raw A code `0x130` is therefore changed
from `BUTTON_A` to direct Android `ENTER`, so the lock screen receives an
explicit confirm/unlock key. This is intentionally a temporary system-UI
policy; a later per-context mapping tool should restore standard gamepad
`BUTTON_A` semantics inside games while retaining an explicit lock-screen
unlock path.
