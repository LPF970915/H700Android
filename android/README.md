# H700 Android workspace

The active product baseline is `h700-android10/`. It combines the H616 Android
10 source and HAL generation with the verified RGSP H700 kernel, DTB, panel,
storage and peripheral facts.

The former R36S-derived Android 11 bring-up files are frozen under
`legacy-android11/`. They remain useful for boot, logging and failure-analysis
reference, but must not supply framework or vendor binaries to the product.

Neither directory is directly flashable. Device writes continue to use the
verified scripts under `device/`, with CID, boot/env hash, filesystem and
readback checks.
