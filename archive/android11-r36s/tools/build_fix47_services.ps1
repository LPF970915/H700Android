$ErrorActionPreference = 'Stop'
[System.Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem') | Out-Null

$smaliRoot = (Resolve-Path 'work\fix44-tools\full-services-smali2').Path
$toolClasspath = (Resolve-Path 'work\fix42-tools').Path + '\*'
$base = (Resolve-Path 'work\fix44-tools\services-fix45.jar').Path
$classes = Join-Path (Get-Location) 'work\fix44-tools\services-classes-fix47.dex'
$out = Join-Path (Get-Location) 'work\fix44-tools\services-fix47.jar'
$tmp = Join-Path (Get-Location) 'work\fix44-tools\services-fix47.tmp.jar'

java -cp $toolClasspath org.jf.smali.Main a $smaliRoot -o $classes
if ($LASTEXITCODE -ne 0) { throw "smali assembly failed: $LASTEXITCODE" }

if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force }
if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }

$src = [System.IO.Compression.ZipFile]::OpenRead($base)
$dst = [System.IO.Compression.ZipFile]::Open($tmp, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  foreach ($entry in $src.Entries) {
    if ($entry.FullName -eq 'classes.dex') { continue }
    $new = $dst.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
    $inStream = $entry.Open()
    $outStream = $new.Open()
    try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
  }

  $new = $dst.CreateEntry('classes.dex', [System.IO.Compression.CompressionLevel]::Optimal)
  $inStream = [System.IO.File]::OpenRead($classes)
  $outStream = $new.Open()
  try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
} finally {
  $dst.Dispose()
  $src.Dispose()
}

Move-Item -LiteralPath $tmp -Destination $out
Get-FileHash -Algorithm SHA256 $classes, $out
