param(
  [Parameter(Mandatory = $true)][string]$BaseBoot,
  [Parameter(Mandatory = $true)][string]$Kernel,
  [Parameter(Mandatory = $true)][string]$Out,
  [string]$Ramdisk = "",
  [string]$Second = "",
  [string]$Dtb = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$parser = Join-Path $PSScriptRoot "android_bootimg.py"
foreach ($path in @($BaseBoot, $Kernel)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing input: $path" }
}

$args = @($parser, "pack", (Resolve-Path -LiteralPath $BaseBoot).Path, (Join-Path $root $Out), "--kernel", (Resolve-Path -LiteralPath $Kernel).Path)
if ($Ramdisk) { if (-not (Test-Path -LiteralPath $Ramdisk -PathType Leaf)) { throw "Missing ramdisk: $Ramdisk" }; $args += @("--ramdisk", (Resolve-Path -LiteralPath $Ramdisk).Path) }
if ($Second) { if (-not (Test-Path -LiteralPath $Second -PathType Leaf)) { throw "Missing second: $Second" }; $args += @("--second", (Resolve-Path -LiteralPath $Second).Path) }
if ($Dtb) { if (-not (Test-Path -LiteralPath $Dtb -PathType Leaf)) { throw "Missing dtb: $Dtb" }; $args += @("--dtb", (Resolve-Path -LiteralPath $Dtb).Path) }

Write-Host "[probe] packing only; no device write will be attempted"
$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
  & py -3 @args
} else {
  & python @args
}
if ($LASTEXITCODE -ne 0) { throw "boot image pack failed: $LASTEXITCODE" }
