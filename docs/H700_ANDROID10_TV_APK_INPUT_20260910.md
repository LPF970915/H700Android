# TV APK and Input Checkpoint

Date: 2026-09-10, host timezone Asia/Shanghai.

## Installed Packages

Read-only UART inspection at host 08:45 confirmed:

| Package | Version | State |
| --- | --- | --- |
| `com.tencent.qqmusictv` | 9.0.0.39 / 9000039 | Installed; AppStarterActivity foreground |
| `com.lonelycatgames.Xplore` | 4.46.00 / 44600 | Installed; navigation acceptance pending |

The user explicitly confirmed manual installation. Earlier unexplained
installer transitions must not be counted as an agent-controlled D-pad pass.
The complete physical-button-only installation sequence was not observed.
The sampled crash buffer was empty; this is not playback or soak acceptance.
SurfaceFlinger/system_server PIDs remain 1494/1926 in this sample.

## Files Input Defects

- User reports physical A does not confirm in Files, while physical Y does.
- Earlier injected directional navigation remained trapped in Files' empty
  Recent view. A nonempty Downloads grid did allow some focus movement.
- File labels were clipped in the Downloads grid at the current screen size.
- The successful Downloads entry used an explicit Files root intent. This
  bootstrap is not a desktop-to-install pure-button workflow.
- A maps to ENTER in the RGSP layout; Y maps to BUTTON_Y. Live Generic.kcm
  supplies BUTTON_Y fallback SPACE. The fallback is a possible explanation,
  not a traced proof of DocumentsUI event handling.
- InputReader reports the physical devices using
  `/system/usr/keylayout/Vendor_0001_Product_0001_Version_0100.kl` and
  `/system/usr/keychars/Generic.kcm`. The attempted vendor ANBERNIC path
  was absent; do not cite that failed read as the active layout.

The test helper now also permits Android BUTTON_Y (100). Key injection
does not prove physical scan-code, device-source, or fallback equivalence.
Do not assume ENTER is universally accepted as confirm across applications.
No global keylayout change is justified solely by this Files observation.

## APK Provenance

APKs were retrieved from developer download pages and copied to
`/sdcard/Download/`; on-device downloading was not tested.

- QQ Music page: `https://y.qq.com/download/download.html`
- QQ Music APK: `https://dldir1.qq.com/music/qqmusictv/10007068_self_32_kg_9.0.0.39_c2a96f72_release_signed.apk`
- QQ Music SHA256: `c37369d85ea817a68e91bb100f1e0994e53b37592c0e80237932f762428128a2`
- X-plore page: `https://www.lonelycatgames.com/apps/xplore`
- X-plore download landing: `https://www.lonelycatgames.com/download/x-plore-4-46-00`
- X-plore SHA256: `1f019bde72fd4b6fefb273e57222d26e27449f36d0ecff370448db205c793a3d`

Local APK metadata reports ARM32 support and compatible minimum SDKs.
QQ Music v1/v2 and X-plore v2/v3 signature verification reports are retained.
Signature validity is not a guarantee of runtime compatibility or safety.

## Remaining Acceptance

Test X-plore first as a user app: physical D-pad focus, A versus Y confirm,
B back, file access prompt, Download navigation, APK opening, install-source
settings round-trip, and return to AT4K. Since QQ Music is installed, label
any subsequent same-version install as an update/reinstall and do not
silently uninstall it.

Test QQ Music initial navigation and any guest playback separately. Login,
payment, audible output, sleep/wake, and physical input remain unaccepted.
No root grant, system/vendor embedding, global remapping, or reboot was
performed for this checkpoint. Review X-plore redistribution licensing and
device usability before deciding on embedding; MT Manager has not been
excluded by a verified compatibility comparison.

## Evidence

Directory: `out/rgsp-qqmusic-tv-dpad-20260910/`.

- `15-installed-state/rgsp_serial_exec_20260910_084523_115200.log`
- `16-key-mapping/rgsp_serial_exec_20260910_084547_115200.log`
- Earlier numbered screenshots, step intents and serial transcripts.
- `apk-badging.txt`, `signature-verification.txt`
- `xplore-badging.txt`, `xplore-signature.txt`

This advances stage 4 to installed-app testing, not stage 4 completion.
Cold boot, TF2-only boot, formal soak and hardware acceptance remain open.
