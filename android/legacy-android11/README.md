# Frozen R36S Android 11 Diagnostic Branch

The Android 11 work is retained only as a bring-up and failure-analysis archive.
It is not an H700 product baseline.

Reusable results include the TF1 handoff, TF2 partitioning, boot/env/CID safety
checks, UART and persistent logging, binder permissions, automatic Linux
fallback, hardware node observations and the fix51-fix58 H616 HAL experiments.

Do not copy the R36S/RK3326 framework, vendor properties, graphics, audio,
media, VINTF declarations or patched framework jars into Android 10. In
particular, all headless `services.jar` and `framework.jar` bypasses are
diagnostic evidence only.

The canonical compressed image retained for binary comparison is documented in
`archive/android11-r36s/README.md`. Historical scripts and logs remain under
`device/`, `tools/`, `docs/` and `out/logs/`.
