# H700 isolated owned-ADC recovery candidate

This candidate starts from frozen `stick_sampling_v2`; `parent-inputs.json`
pins its five production inputs and Test9 module. Nothing in Test8/Test9 or
their receipts is replaced. This source change has not been physically tested.

The latest report is that both RG34XXSP and RG35XX H have no stick response.
Test8's captured Linux capabilities included the analog axes, but physical
operations produced neither axes nor L3/R3. No ADC registers were captured at
failure. Consequently this candidate repairs demonstrated failure paths in
the code, not an established hardware root cause for those two machines.

The earlier working RG34XXSP driver continuously sampled the same ADC and GPIO
wiring. Test8 added ADC readiness checks that could disable polling forever;
Test9 rechecked the state but never restored the already managed ADC. Both
versions also blocked the independent GPIO stick switches while ADC readiness
failed. This candidate keeps the existing twelve profiles and applies:

- GPIO L3/R3 release gating and two-sample debounce before ADC checks. ADC
  failure neutralizes only analog axes and leaves clicks operating at 10 ms.
- ADC control/selection loss, or a real PM POST event, requests the same ADC
  setup sequence used at cold startup. Recovery never resamples the saved
  centers. Each stick needs three actual neutral ADC frames before rearming.
- Recovery requires the original GPADC DT node to remain disabled and all
  module GPIO claims/maps to remain held. Any non-channel-0 selection or
  comparator field is evidence of other use and prohibits ADC writes. These
  guards also protect ADC restoration on module exit.
- CCU clock/reset readiness is checked before ADC reads or writes; the module
  never writes CCU. Closed clocks keep axes neutral while polling continues.
- Configuration writes are at least one second apart, including across PM.
  Three writes without a full second of continuous healthy actual sampling
  exhaust the recovery budget and leave a read-only quarantine. A real PM
  POST starts a new budget; an external restoration that stays healthy for a
  second also clears it. A momentarily successful readback cannot repeatedly
  reset the budget while another component keeps changing the ADC.
- Fixed diagnostics retain their one-second absolute log limit and 5/60-second
  blocked/healthy cadence, adding channel selection, recovery counters and
  current PI/PE configuration/data fields.

GPIO claims establish the kernel ownership tracked by this module, not that
unrelated bare-MMIO code has left every GPIO mux/value unchanged. Recovery
does not rewrite GPIO muxes, acquire clocks, or take over an enabled ADC node.
The positive other-channel check cannot detect unrelated bare-MMIO users that
reuse exactly channel 0. The bounded budget limits such unobservable conflict.
Future physical diagnostics must distinguish ADC state loss from GPIO mux,
enable-line, timing, or other hardware failures before claiming full repair.

No-stick profiles continue to exit before hardware access. RG40XX V remains a
single-stick profile and never requests or samples the right-stick pins/axes.
PM PRE still cancels work and releases all axes and clicks. The isolated host
fixture uses actual Linux PM integer values 1 through 6, and the actual C file
is exercised against a counted MMIO/GPIO API boundary. Such tests validate
control flow and safety guards; they cannot certify real register retention,
physical timing, stick directions, or a complete image on hardware.
