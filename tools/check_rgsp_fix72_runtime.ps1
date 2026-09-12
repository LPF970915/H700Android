#requires -Version 7.2
[CmdletBinding()]
param(
    [string]$Port = 'COM4',
    [int]$TimeoutSeconds = 120,
    [ValidateSet('Frozen', 'Codec', 'Audio')][string]$Profile = 'Frozen'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifest = Join-Path $root 'out/rgsp-fix72-wifi-profile/CONTENT_CHECKS.json'
if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    'e2f7a4172d219276365b64c317dac9b6c9a41f48f528c4d72a8400bd4ed4769b') {
    throw 'The frozen Fix72 component manifest changed.'
}
$checks = @(Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json)
if ($checks.Count -ne 17) { throw 'Expected exactly 17 frozen components.' }
if ($Profile -in @('Codec', 'Audio')) {
    $checks += @(
        @{ partition = 'vendor'; path = 'etc/media_codecs.xml'; sha256 = '152e5797f0b9a27101faf43614b438f6b75022e9c24423e333582dccbbaed3b4' },
        @{ partition = 'vendor'; path = 'etc/media_codecs_google_audio.xml'; sha256 = 'f33464aee38c30e1fe52764bdb1d98ccd56a8214618d03b061b0fd63c38b0000' },
        @{ partition = 'vendor'; path = 'etc/media_codecs_google_video.xml'; sha256 = '876f5f850cbb5ce4f7a9582654ce006888903e6016dd0b8053e61ab0fd993839' }
    )
}
if ($Profile -eq 'Audio') {
    $checks += @(
        @{ partition = 'vendor'; path = 'etc/audio_mixer_paths.xml'; sha256 = 'b2d44f61da7a748ae0beae89639de41d70c9b4397d500cd1aeb88a5ea725d870' },
        @{ partition = 'vendor'; path = 'ueventd.rc'; sha256 = 'c59ed9aaf33e260bb61bf003c8f0526df255a87adb16d7300964432d021ab6f9' },
        @{ partition = 'vendor'; path = 'bin/rgsp-input-prepare.sh'; sha256 = '0cc985b7aff4a70401fa39021cc7a645e6300246381dea51f58646cbc3da2cbe' }
    )
}
$lines = foreach ($entry in $checks) {
    if ($entry.partition -notin @('system', 'vendor') -or
        $entry.path -notmatch '^[A-Za-z0-9_./-]+$' -or
        $entry.path -match '(^|/)\.\.(/|$)' -or
        $entry.sha256 -notmatch '^[a-f0-9]{64}$') {
        throw 'Unsupported manifest entry.'
    }
    $prefix = if ($entry.partition -eq 'vendor') { '/vendor/' } else { '/' }
    "$($entry.sha256)  $prefix$($entry.path)"
}
$outputDirectory = 'out/logs/uart/rgsp-fix72-runtime-' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$helper = Join-Path $PSScriptRoot 'invoke_rgsp_serial_command.ps1'
function Invoke-Check([string]$Command) {
    $Command = $Command.Replace("`r`n", "`n").Replace("`r", "`n")
    & ([Environment]::ProcessPath) -NoProfile -File $helper -Port $Port `
        -ShellPath /system/bin/sh -Command $Command -TimeoutSeconds $TimeoutSeconds `
        -OutputDirectory $outputDirectory
    if ($LASTEXITCODE -ne 0) { throw "Runtime check failed (exit $LASTEXITCODE)." }
}

Push-Location $root
try {
    Invoke-Check @'
set -eu
test "$(id -u)" = 0
test "$(getprop ro.product.device)" = rgsp
test "$(getprop sys.boot_completed)" = 1
test "$(cat /sys/block/mmcblk0/device/cid)" = 1d414455534400002000009f9401a1e7
test "$(cat /sys/block/mmcblk1/device/cid)" = fe3432534400000020000005bc01896b
awk '$2 == "/" && $1 == "/dev/mmcblk1p2" && $3 == "ext4" && $4 ~ /^ro,/ { n++ } END { exit(n!=1) }' /proc/mounts
awk '$2 == "/vendor" && $1 == "/dev/mmcblk1p3" && $3 == "ext4" && $4 ~ /^ro,/ { n++ } END { exit(n!=1) }' /proc/mounts
awk '$2 == "/data" && $1 == "/dev/mmcblk1p4" && $3 == "ext4" && $4 ~ /^rw,/ { n++ } END { exit(n!=1) }' /proc/mounts
awk '$2 == "/rgsp-persist" && $1 == "/dev/mmcblk1p1" && $3 == "vfat" { n++ } END { exit(n!=1) }' /proc/mounts
echo FIX72_RUNTIME_IDENTITY_OK
cat /proc/uptime
cat /proc/sys/kernel/random/boot_id
for service in surfaceflinger zygote system_server; do
    printf '%s=' "$service"
    pidof "$service"
done
'@
    $checksumCommand = "set -eu; printf '%s\n' '" + ($lines -join "' '") +
        "' | sha256sum -c -; echo FIX72_COMPONENTS_$($checks.Count)_OK"
    Invoke-Check $checksumCommand
    if ($Profile -in @('Codec', 'Audio')) {
        Invoke-Check @'
set -eu
awk '$2 == "/vendor/etc" || $2 == "/vendor/odm/etc" || index($2,"/vendor/etc/")==1 || index($2,"/vendor/odm/etc/")==1 { n++ } END { exit(n!=0) }' /proc/mounts
test "$(getprop init.svc.vendor.media.omx)" = running
test "$(getprop init.svc.media)" = running
echo FIX72_CODEC_PERSISTENT_FILES_OK
'@
    }
    if ($Profile -eq 'Audio') {
        Invoke-Check @'
set -eu
awk '$2 == "/vendor/ueventd.rc" || $2 == "/vendor/bin" || index($2,"/vendor/bin/")==1 { n++ } END { exit(n!=0) }' /proc/mounts
for node in /dev/snd/controlC0 /dev/snd/pcmC0D0p; do
    test -c "$node"
    test "$(stat -c '%u:%g:%a' "$node")" = 1000:1005:660
done
pidof audioserver
echo FIX72_AUDIO_PERSISTENT_FILES_AND_NODES_OK
'@
    }
    Invoke-Check @'
set -eu
test "$(sha256sum /dev/mmcblk0p4 | cut -d ' ' -f 1)" = d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
test "$(sha256sum /rgsp-persist/rgsp-linux-boot-original.img | cut -d ' ' -f 1)" = d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
test "$(dd if=/dev/mmcblk0p3 bs=131072 count=1 2>/dev/null | sha256sum | cut -d ' ' -f 1)" = d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396
test ! -e /rgsp-persist/RGSP_ANDROID_TRY.ONCE
echo FIX72_LINUX_RECOVERY_OK
sh /system/bin/rgsp-firstboot.sh status
home=$(cmd package resolve-activity --brief --user 0 -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1)
test "$home" = com.overdevs.at4k/.MainActivity
test "$(settings --user 0 get secure default_input_method)" = com.android.inputmethod.leanback/.service.LeanbackImeService
pm path com.android.launcher3 | grep '^package:'
pm path com.android.inputmethod.latin | grep '^package:'
for package in com.overdevs.at4k com.android.inputmethod.leanback; do
    apk=$(pm path "$package" | sed -n 's/^package://p' | head -n 1)
    case "$package" in
        com.overdevs.at4k) expected=1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9 ;;
        *) expected=2a57b52cbac36d09138f7d94ba43f5d7fa9c4175966f7f1b43bb004b1a83ff18 ;;
    esac
    test "$(sha256sum "$apk" | cut -d ' ' -f 1)" = "$expected"
    echo "ACTIVE_APK_OK=$package"
done
echo FIX72_PREFERENCES_OK
head -n 5 /proc/meminfo
df -k /data
echo CRASH_BUFFER_LINE_COUNT
crash=$(logcat -b crash -d -t 100 2>/dev/null)
if [ -n "$crash" ]; then
    printf '%s\n' "$crash" | wc -l
    echo FIX72_CRASH_BUFFER_NONEMPTY_REVIEW_REQUIRED >&2
    exit 1
else
    echo 0
fi
'@
    Write-Host "FIX72_RUNTIME_READONLY_OK: $outputDirectory"
    Write-Host 'Not a cold-boot, visual, audio, physical-input, or soak acceptance.'
} finally {
    Pop-Location
}
