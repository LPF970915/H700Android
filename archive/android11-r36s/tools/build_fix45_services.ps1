$ErrorActionPreference = 'Stop'
[System.Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem') | Out-Null
$base = (Resolve-Path 'work\fix44-tools\services-display-bypass.jar').Path
$classes2 = (Resolve-Path 'work\fix44-tools\classes2-fix45.dex').Path
$out = Join-Path (Get-Location) 'work\fix44-tools\services-fix45.jar'
$tmp = Join-Path (Get-Location) 'work\fix44-tools\services-fix45.tmp.jar'
if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force }
if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }
$src = [System.IO.Compression.ZipFile]::OpenRead($base)
$dst = [System.IO.Compression.ZipFile]::Open($tmp, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  foreach ($entry in $src.Entries) {
    if ($entry.FullName -eq 'classes2.dex') { continue }
    $new = $dst.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
    $inStream = $entry.Open()
    $outStream = $new.Open()
    try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
  }
  $new = $dst.CreateEntry('classes2.dex', [System.IO.Compression.CompressionLevel]::Optimal)
  $inStream = [System.IO.File]::OpenRead($classes2)
  $outStream = $new.Open()
  try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
} finally { $dst.Dispose(); $src.Dispose() }
Move-Item -LiteralPath $tmp -Destination $out
Get-FileHash -Algorithm SHA256 $out
