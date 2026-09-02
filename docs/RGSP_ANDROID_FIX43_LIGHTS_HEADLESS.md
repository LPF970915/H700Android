# RGSP H700 Android fix43

fix42 proved that the patched `system_server` and `zygote64` can stay alive, but
the framework Watchdog killed `system_server` after about 183 seconds. The
deterministic main-thread stack was:

```text
LightsService.populateAvailableLightsFromHidl
  -> SurfaceControl.nativeGetPhysicalDisplayIds
  -> SystemServer.startBootstrapServices
```

Because fix41/fix42 deliberately isolate SurfaceFlinger, this synchronous
display query can never complete. fix43 removes only the `LightsService` startup
call from `SystemServer`; the timing trace remains, and all other fix42 changes
are retained. This is still a headless framework diagnostic and does not create
a visible desktop or a software framebuffer.

The candidate services JAR SHA-256 is
`65ba4eb5ad72e9c14bfa467b0ba1d358baa79a1adf8c77729e7fc970e5b3c091`.
No device write has been performed by preparing this candidate.
