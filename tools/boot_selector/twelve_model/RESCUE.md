# Manual panel trial components

The normal picker retains all twelve models and ten complete electrical
profiles. This isolated revision adds a manual volume gesture while the picker
is running. It does not identify the connected model from RAM, geometry,
framebuffer size, serial numbers or stored identity.

Volume Down advances through rg35xxh → rg34xxsp → rgcubexx → rg35xxh;
Volume Up takes the reverse direction. The initialized model's logical geometry
selects the current group, independently of the highlighted model. The first
unsaved boot still initializes the complete RG35XX H 640×480 profile.

A fresh volume press and release lasting 20–2000 ms requests one trial. Startup
held keys, kernel repeat events, dropped input synchronization and simultaneous
volume keys do not request a trial. The program writes the schema 2 result with
save_default=false and exits 4. It paints a transition message if fbdev works.
If fbdev cannot be opened or its ioctls fail, it keeps receiving volume gestures
and refuses ordinary Start; this does not prove physical panel compatibility.

The new boot-state preview command accepts only the three representatives,
preserves roc_saved_model and stores roc_next_model with roc_next_start=2.
The early bridge re-enters the selector on that profile. Marker 2 remains
persisted while waiting: power loss and the next boot return to the same trial
menu. Normal explicit confirmation consumes it through clear-next, save or
ordinary once (marker 1). Neither boot component advances the trial cycle
automatically.

For exit 4, the hook checks the adjacent representative, verifies the unchanged
saved model and reads back marker 2 before requesting a reboot. Result parsing,
state writing or readback failure returns to manual selection. Unsafe output
files, failed cleanup/synchronization and an unexpectedly returning reboot
enter a waiting loop. General historical selector errors retain the original
parent init's diagnostic Android behavior.

Offline verification compiles final host and static AArch64 programs, runs both
ELFs, and uses ordinary file/FIFO fixtures only. Successful fixture reboots use
an explicitly recorded no-return exec boundary. Unexpected returns run the
actual waiting-loop branch, bounded by a fixture sleep 60 stub exiting 78.
These are API boundaries, not simulated Linux reboot or physical input proof.
The final normal Start receipt is produced after the menu receipt is frozen
and is bound separately by the packaging manifest, avoiding a hash cycle.
