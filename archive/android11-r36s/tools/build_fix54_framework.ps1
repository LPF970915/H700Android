$ErrorActionPreference = 'Stop'

[System.Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem') | Out-Null

$root = (Resolve-Path 'work\fix54-tools').Path
$base = Join-Path $root 'framework-original.jar'
$originalClasses = Join-Path $root 'classes3.dex'
$classes = Join-Path $root 'classes3-fix54-binary.dex'
$out = Join-Path $root 'framework-fix54.jar'
$tmp = Join-Path $root 'framework-fix54.tmp.jar'
$originalDexSha = 'F4E1EDCABAD5A94BC8206A8467514118009C5CF6A2D83ECDF89F430B6A260E8D'
$codeOffset = 0x23ed84

function Convert-HexToBytes([string]$hex) {
  $clean = $hex -replace '\s', ''
  if (($clean.Length % 2) -ne 0) { throw 'hex string has an odd length' }
  $bytes = [byte[]]::new($clean.Length / 2)
  for ($i = 0; $i -lt $bytes.Length; $i++) {
    $bytes[$i] = [Convert]::ToByte($clean.Substring($i * 2, 2), 16)
  }
  return $bytes
}

if ((Get-FileHash -Algorithm SHA256 $originalClasses).Hash -ne $originalDexSha) {
  throw 'unexpected original classes3.dex hash'
}

$bytes = [IO.File]::ReadAllBytes($originalClasses)
$expected = Convert-HexToBytes @'
71 00 04 07 00 00 0c 00 12 01 6e 20 03 07 10 00 0c 00
6e 10 75 3f 00 00 0c 00 6e 10 80 3e 00 00 0a 00 0f 00
'@

for ($i = 0; $i -lt $expected.Length; $i++) {
  if ($bytes[$codeOffset + $i] -ne $expected[$i]) {
    throw ('unexpected getRefreshRate byte at 0x{0:x}' -f ($codeOffset + $i))
  }
}

$replacement = [byte[]]::new($expected.Length)
$prefix = Convert-HexToBytes '15 00 70 42 0f 00'
[Array]::Copy($prefix, 0, $replacement, 0, $prefix.Length)
[Array]::Copy($replacement, 0, $bytes, $codeOffset, $replacement.Length)

$sha1 = [Security.Cryptography.SHA1]::Create()
try {
  $signature = $sha1.ComputeHash($bytes, 32, $bytes.Length - 32)
} finally {
  $sha1.Dispose()
}
[Array]::Copy($signature, 0, $bytes, 12, $signature.Length)

$a = 1
$b = 0
for ($i = 12; $i -lt $bytes.Length; $i++) {
  $a = ($a + [int]$bytes[$i]) % 65521
  $b = ($b + $a) % 65521
}
$checksum = [uint32](([uint64]$b * 65536) + [uint64]$a)
$checksumBytes = [BitConverter]::GetBytes($checksum)
[Array]::Copy($checksumBytes, 0, $bytes, 8, 4)

[IO.File]::WriteAllBytes($classes, $bytes)

if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force }
if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }

$src = [System.IO.Compression.ZipFile]::OpenRead($base)
$dst = [System.IO.Compression.ZipFile]::Open($tmp, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  foreach ($entry in $src.Entries) {
    if ($entry.FullName -eq 'classes3.dex') { continue }
    $new = $dst.CreateEntry($entry.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
    $inStream = $entry.Open()
    $outStream = $new.Open()
    try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
  }

  $new = $dst.CreateEntry('classes3.dex', [System.IO.Compression.CompressionLevel]::Optimal)
  $inStream = [System.IO.File]::OpenRead($classes)
  $outStream = $new.Open()
  try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose(); $inStream.Dispose() }
} finally {
  $dst.Dispose()
  $src.Dispose()
}

Move-Item -LiteralPath $tmp -Destination $out
Get-FileHash -Algorithm SHA256 $classes, $out
