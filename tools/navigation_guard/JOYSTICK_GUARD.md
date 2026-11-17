# Isolated joystick navigation candidate (2026-11-15)

This candidate changes the Java fallback in Android 10 `ViewRootImpl`. It does
not patch the input driver or `InputDispatcher`, and it is not an installable
framework or a system image. Ordinary hardware DPAD keys require the separate
DPAD candidate; the joystick guard emits local `FLAG_FALLBACK` events with a
private `QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED` provenance bit. Other
trackball or keyboard fallback events do not inherit that bit and must not
automatically bypass the independent DPAD guard.

`apply_joystick_guard.py` accepts only this retained source SHA256:

`0eadf38bc8ceb599dcf57eb2d6a8b9e818a19ecedca1143b3a361682c0e64639`

It writes a complete candidate, unified patch and manifest only to a new work
directory. It never writes the source file, Android output, image or manifest.
It preserves the original `SyntheticJoystickHandler` body except for scoped
routing to the new helper. The host runner strips the routing and verifies the
remaining legacy class byte for byte against the retained source.

## Scope and behavior

The exact package allowlist is `com.overdevs.at4k`, `com.android.settings`,
`com.android.documentsui`, and `com.android.systemui`. Other applications keep
the retained legacy fallback, including its ordinary long holds. Scope is read
from this ViewRoot's context, never from the focused application's label.

State is isolated by device ID and source. X, Y, HAT_X and HAT_Y have separate
observed neutral and blocked states. HAT has priority on its dimension; a stick
that was deflected during HAT use cannot take over until it visits neutral.
X and Y have separate held keys and callback tokens. Z/RZ are not synthesized.
The retained inclusive +/-0.5 threshold is unchanged. A short press emits one
immediate DOWN. Navigation begins long-press repeat after 400ms, then repeats
every 160ms. Excluded applications retain their original timing.

The first accepted deflection starts one absolute 10 second session for that
device/source. Repeated MOVE, direction reversal and HAT takeover do not extend
it. An independent deadline message stops it even if no new MOVE arrives.
Stops remove only their own callback tokens and emit one balanced local UP per
accepted held key, retaining its original downTime. Cancellation uses CANCELED.
Every observed nonzero channel at a stop must subsequently supply a valid
neutral sample. A previously neutral or unknown channel accepts its first new
press normally. Nonfinite samples cannot unlock a channel.

Navigation requires both window focus and actual `Display.STATE_ON`. The patch
forwards the real `DisplayListener.onDisplayChanged`, matching display removal,
and display moves through the synthetic stage, with a null-safe cast because
the actual retained field is declared as `InputStage`. OFF, DOZE and other
states cannot continue repeats despite retained focus. Existing focus-loss,
prior-consumer and detach hooks still call `cancel`. The prior-consumer hook
cancels only that event's device/source identity and observes its valid current
MOVE; it cannot erase another controller's repeat. The actual
`setWindowStopped(true)` method also forwards cancellation. A view must be
attached, present, and not stopped. The current display must also exist and
remain valid; a removed display cannot restart a previously neutral channel
while the cached display state still says ON. Future, negative, pre-boundary or
out-of-order sample times cannot discharge neutral debt. Each identity records
its own stop boundary as well as its latest accepted sample time, so a late
neutral that predates a timeout or CANCEL cannot unlock that channel. A repeat callback also
checks device presence and declared source capability before emitting.

The real post-IME key method also validates each guarded event before window
dispatch. The private queue bit is only provenance: a registered KeyEvent object
and its sequence number must match a delivery token. A DOWN must still belong
to the current session epoch and arrive before the held key's immutable
deadline. Focus/display cancellation invalidates even a DOWN that was already
queued or waiting on an earlier input stage. A late old event cannot cancel a
new held key. A natural release does not invalidate its own epoch, preserving
a valid short DOWN/UP tap that was queued before either event reached the gate.
An UP may balance only a DOWN that passed that gate, once. If an earlier input
stage consumed the initial DOWN, its repeats cannot replace that initial DOWN
and no orphan UP is delivered. The actual `finishInputEvent` path removes the
token before event or queue recycling, including earlier consumed/dropped
events; a recycled queue record cannot inherit authorization. Here "delivered"
means admission to the post-IME window dispatch path. It does not establish
that an application or IME consumed both halves of a press symmetrically.

Events remain in the same ViewRoot's queue. No system input injection, settings,
signature, SELinux, framework restart or device action is part of this work.
If an earlier input stage discards the only physical neutral sample, this
handler cannot reconstruct it. The original missing-event path has not been
captured on the reporting user's device.

## Validation

Run `tools/navigation_tests/test_native_joystick_candidate.py` through the fixed
`tools/public_build/run-limited.sh` wrapper, with the retained source, a fresh
work directory, and the repository Android JDK9 `javac`/`java` paths. The runner
checks SHA binding and a mutated-source negative control, deterministic
generation and byte-exact legacy preservation. It executes the actual guard,
legacy class, `SyntheticInputStage`, `DisplayListener` and moved-display method
inside explicit virtual Android/scheduling doubles. It also extracts and runs
the actual post-IME `processKeyEvent` and `finishInputEvent` methods so the
delivery and cleanup hooks are exercised at their real source locations.

The scenarios cover independent 10 second deadlines, duplicate/reverse MOVE,
HAT/stick arbitration, X/Y cancellation isolation, devices/sources, focus and
display state as separate signals, display removal/move/early initialization,
nonfinite values, old callback tokens, device disappearance/reconnection,
batched history and lifecycle boundaries, all four exact scoped packages,
excluded games/packages, right-stick semantics, and existing consumer/detach
hooks, fixed navigation timing, rejected timestamps, and stopped/absent views.
Delayed delivery controls cover ordinary short taps, all DOWNs deferred past
the absolute deadline, expiry before timer callbacks run, OFF/ON and focus
epochs, old repeats and balanced UPs arriving after a new press, an initial DOWN
consumed upstream, forged provenance, sequence changes, and queue reuse. A
destroyed root drops even terminal events at the original InputStage boundary;
that case checks cleanup rather than claiming an UP can reach a removed view.
Host tests do not establish physical suspend/resume behavior or prove
which input path caused the video. A real Android API compile and coordinated
framework/preopt build are separate requirements before making an installable
artifact; replacing only `framework.jar` is not an accepted deployment method.
