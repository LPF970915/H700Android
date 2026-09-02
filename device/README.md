# Mainline Device Utilities

Only hardware-neutral or Android 10 reusable device-side utilities remain here:

- `format_tf2_android.sh`: guarded TF2 partition preparation;
- `read-only-inventory.sh`: non-destructive hardware inventory.

The R36S Android 11 fix6-fix58 deployment, patch and handoff scripts are frozen
under `archive/android11-r36s/device/`. They are diagnostic records and must not
be used as Android 10 product dependencies.
