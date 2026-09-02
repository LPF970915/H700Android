# RGSP H700 Android fix41

fix40 proved that the GLES-only SurfaceFlinger path was the immediate crash source and that `system_server` can be created when SurfaceFlinger is isolated. fix41 enables Android framework headless mode with:

```
ro.config.headless=1
```

This is intended to let Android framework services finish boot without a SurfaceFlinger instance. It does not provide a visible desktop, EGL, GLES, HWC, or framebuffer output. The existing fix40 SurfaceFlinger service isolation remains unchanged.

The test reuses the verified fix32 boot image and retains all device safety gates: TF1/TF2 CID checks, original boot/env hashes, TF2 `e2fsck -fn`, read-only system verification, one-shot marker, full boot write readback, and automatic Linux recovery through the handoff ramdisk.
