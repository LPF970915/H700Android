# RG SP H700 Graphics Status (2026-08-30)

## Deterministic findings

- The only Android GPU blob available locally is `system/vendor/lib64/egl/libGLES_mali.so` from the R36S image. Its embedded paths identify `hardware/rockchip/mali_so` and an RK3326/R21 userspace stack.
- The H700 kernel exposes `/dev/mali0` through `mali_kbase` for Mali-G31. The Android blob therefore remains an ABI-mismatch candidate and is not copied into any new image.
- The R36S Android system image contains no `libGLES_android.so`, `libEGL_swiftshader.so`, or `libGLESv2_swiftshader.so` for ARM64. The Android SDK SwiftShader files present on the host are Windows/x86 emulator binaries and are not usable on H700.
- Android 11 `libsurfaceflinger.so` in the image selects the GLES RenderEngine. The binary has no usable software framebuffer backend that can be enabled by a property alone.

## Fix40 diagnostic branch

`apply_rgsp_android_fix40_nogpu_diag.sh` is a reversible, evidence-driven diagnostic. It backs up every SurfaceFlinger rc file, inserts `disabled`, removes the zygote-killing `onrestart` hook, and comments every explicit `start surfaceflinger` line found in Android rc files. This isolates `zygote/system_server` from the known GLES crash loop.

The matching prepare script reuses the verified fix32 boot image and retains all existing protections: root/CID checks, original boot/env hashes, TF2 `e2fsck -fn`, one-shot marker, complete boot readback, and automatic rollback through the existing watcher.

This branch is expected to prove whether `system_server` can run without SurfaceFlinger. It is **not** yet a desktop solution: a real ARM64 software EGL/GLES implementation or a custom fbdev composer is still required for a visible Android UI.
