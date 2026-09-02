$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$src = Join-Path $root 'work/h700-source-analysis/h616/image-extract/vendor-root-fix51'
$base = Join-Path $root 'out/fix51-h616/payload'
$overlay = Join-Path $root 'out/fix57-h616-audio-bypass/payload'
$out = Join-Path $root 'out/fix58-h616-audio-h616-baseline/payload'
if (!(Test-Path $src)) { throw "Missing H616 extracted vendor tree: $src" }
if (!(Test-Path $base)) { throw "Missing fix57 payload baseline: $base" }
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null
Copy-Item -Recurse -Force (Join-Path $base '*') $out
if (Test-Path $overlay) { Copy-Item -Recurse -Force (Join-Path $overlay '*') $out }

function Copy-Rel([string]$from, [string]$to) {
  $dst = Join-Path $out $to
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item -Force (Join-Path $src $from) $dst
}

# H616 Android 10 audio service, HAL and policy files.
Copy-Rel 'bin/hw/android.hardware.audio@2.0-service' 'system/vendor/bin/hw/android.hardware.audio@2.0-service'
Copy-Rel 'lib/hw/android.hardware.audio@5.0-impl.so' 'system/vendor/lib/hw/android.hardware.audio@5.0-impl.so'
Copy-Rel 'lib/hw/android.hardware.audio.effect@5.0-impl.so' 'system/vendor/lib/hw/android.hardware.audio.effect@5.0-impl.so'
Copy-Rel 'lib/hw/audio.primary.cupid.so' 'system/vendor/lib/hw/audio.primary.cupid.so'
Copy-Rel 'lib/hw/audio.primary.cupid.so' 'system/vendor/lib/hw/audio.primary.rk3326.so'
Copy-Rel 'lib/hw/audio.primary.default.so' 'system/vendor/lib/hw/audio.primary.default.so'
Copy-Rel 'lib/libtinyalsa_audio.so' 'system/vendor/lib/libtinyalsa_audio.so'
Copy-Rel 'lib/libwebrtc_audio_preprocessing.so' 'system/vendor/lib/libwebrtc_audio_preprocessing.so'
Copy-Rel 'lib/soundfx/libaudiopreprocessing.so' 'system/vendor/lib/soundfx/libaudiopreprocessing.so'
Copy-Rel 'lib/android.hardware.audio.common-util.so' 'system/vendor/lib/android.hardware.audio.common-util.so'
Copy-Rel 'lib/android.hardware.audio.common@5.0-util.so' 'system/vendor/lib/android.hardware.audio.common@5.0-util.so'

foreach ($name in @('audio_policy_configuration.xml','audio_platform_info.xml','audio_mixer_paths.xml','audio_effects.xml','a2dp_audio_policy_configuration.xml','usb_audio_policy_configuration.xml','r_submix_audio_policy_configuration.xml','audio_policy_volumes_drc.xml','default_volume_tables.xml')) {
  Copy-Rel "etc/$name" "system/vendor/etc/$name"
}
# Android 11's policy manager prefers the nested /vendor/etc/audio location;
# keep both locations on the same H616 policy to avoid selecting the stale
# RK3326 policy left by the alpha system.
New-Item -ItemType Directory -Force (Join-Path $out 'system/vendor/etc/audio') | Out-Null
Copy-Item -Force (Join-Path $src 'etc/audio_policy_configuration.xml') (Join-Path $out 'system/vendor/etc/audio/audio_policy_configuration.xml')
foreach ($name in @('a2dp_audio_policy_configuration.xml','usb_audio_policy_configuration.xml','r_submix_audio_policy_configuration.xml','audio_policy_volumes_drc.xml','default_volume_tables.xml')) {
  Copy-Item -Force (Join-Path $src "etc/$name") (Join-Path $out "system/vendor/etc/audio/$name")
}
Copy-Rel 'etc/init/android.hardware.audio@2.0-service.rc' 'system/vendor/etc/init/android.hardware.audio@2.0-service.rc'

# Switch the two audio HAL entries in the active manifest from the accidental @6.0
# declaration back to the H616 Android 10 @5.0 contract.
$manifest = Join-Path $out 'system/vendor/etc/vintf/manifest.xml'
$xml = Get-Content $manifest -Raw
$xml = [regex]::Replace($xml, '(?s)<hal format="hidl">\s*<name>android\.hardware\.audio</name>.*?</hal>', @'
    <hal format="hidl">
        <name>android.hardware.audio</name>
        <transport>hwbinder</transport>
        <version>5.0</version>
        <interface><name>IDevicesFactory</name><instance>default</instance></interface>
        <fqname>@5.0::IDevicesFactory/default</fqname>
    </hal>
'@, 1)
$xml = [regex]::Replace($xml, '(?s)<hal format="hidl">\s*<name>android\.hardware\.audio\.effect</name>.*?</hal>', @'
    <hal format="hidl">
        <name>android.hardware.audio.effect</name>
        <transport>hwbinder</transport>
        <version>5.0</version>
        <interface><name>IEffectsFactory</name><instance>default</instance></interface>
        <fqname>@5.0::IEffectsFactory/default</fqname>
    </hal>
'@, 1)
Set-Content -NoNewline -Encoding utf8 $manifest $xml

$delete = Join-Path $out 'DELETE_PATHS.txt'
[IO.File]::WriteAllText($delete, "system/vendor/etc/init/android.hardware.audio.service.rc.rk3326-disabled`n", [Text.Encoding]::ASCII)
$manifestPath = Join-Path $out 'PAYLOAD.sha256'
Push-Location $out
try {
  $lines = @(Get-ChildItem -Recurse -File | Where-Object { $_.Name -ne 'PAYLOAD.sha256' } | ForEach-Object {
    (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower() + '  ' + $_.FullName.Substring($out.Length + 1).Replace('\','/')
  } | Sort-Object)
  [IO.File]::WriteAllText($manifestPath, (($lines -join "`n") + "`n"), [Text.Encoding]::ASCII)
}
finally { Pop-Location }
$tar = Join-Path (Split-Path $out) 'fix58-h616-audio-h616-baseline-payload.tar.gz'
if (Test-Path $tar) { Remove-Item -Force $tar }
tar -czf $tar -C $out .
Get-FileHash $tar -Algorithm SHA256 | Format-Table -AutoSize
Write-Output "PAYLOAD=$out"
Write-Output "ARCHIVE=$tar"
Write-Output "MANIFEST=$manifestPath"
