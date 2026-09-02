# RGSP H700 Android fix42

fix41 reached a live `system_server`, but its Watchdog thread aborted while
querying the absent HIDL ServiceManager. The stack ended in
`android.hidl.manager.V1_0.IServiceManager.getService`, so this version applies
one narrow framework change: `com.android.server.Watchdog.getInterestingHalPids()`
returns an empty list during H700 bring-up instead of calling the unavailable
HIDL manager.

This is a diagnostic framework step. It does not claim that SurfaceFlinger,
`package_native`, `systemReady`, or a visible Android desktop are solved. The
fix41 headless property and disabled SurfaceFlinger service remain unchanged.

The patched `services.jar` is rebuilt from the original jar's first dex and
keeps the second dex and all resource entries. Before any device write, the
candidate is verified locally by re-disassembling the patched Watchdog method.
The device scripts retain CID, original boot/env hash, `e2fsck -fn`, one-shot
marker, write-readback, and automatic Linux fallback checks.
