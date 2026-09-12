[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [int]$DiskNumber,
    [string]$SystemImage = 'system.raw.img',
    [string]$VendorImage = 'vendor.raw.img'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$systemPath = (Resolve-Path (Join-Path $root $SystemImage)).Path
$vendorPath = (Resolve-Path (Join-Path $root $VendorImage)).Path
$diskPath = "\\.\PhysicalDrive$DiskNumber"
$expectedDiskBytes = 125069950976L
$systemOffset = 269484032L
$systemBytes = 8589934592L
$vendorOffset = 8859418624L
$vendorBytes = 2147483648L

if (!(Test-Path -LiteralPath $systemPath -PathType Leaf)) { throw "Missing system image: $systemPath" }
if (!(Test-Path -LiteralPath $vendorPath -PathType Leaf)) { throw "Missing vendor image: $vendorPath" }
$disk = Get-Disk -Number $DiskNumber
if ($disk.BusType -ne 'USB') { throw "Refusing non-USB disk $DiskNumber ($($disk.BusType))" }
if ([int64]$disk.Size -ne $expectedDiskBytes) { throw "Refusing unexpected disk size $($disk.Size)" }
if ($disk.PartitionStyle -ne 'GPT') { throw 'Refusing non-GPT disk' }

$partitions = @(Get-Partition -DiskNumber $DiskNumber)
$systemPart = $partitions | Where-Object PartitionNumber -eq 2
$vendorPart = $partitions | Where-Object PartitionNumber -eq 3
if ($null -eq $systemPart -or [int64]$systemPart.Offset -ne $systemOffset -or [int64]$systemPart.Size -ne $systemBytes) {
    throw 'Partition 2 geometry mismatch'
}
if ($null -eq $vendorPart -or [int64]$vendorPart.Offset -ne $vendorOffset -or [int64]$vendorPart.Size -ne $vendorBytes) {
    throw 'Partition 3 geometry mismatch'
}
if ((Get-Item -LiteralPath $systemPath).Length -ne $systemBytes) { throw 'system raw image size mismatch' }
if ((Get-Item -LiteralPath $vendorPath).Length -ne $vendorBytes) { throw 'vendor raw image size mismatch' }

Write-Host "TARGET=$diskPath SIZE=$($disk.Size)"
Write-Host "SYSTEM=$systemPath OFFSET=$systemOffset BYTES=$systemBytes"
Write-Host "VENDOR=$vendorPath OFFSET=$vendorOffset BYTES=$vendorBytes"
Write-Host 'The next confirmation is the final write gate.'
if (!$PSCmdlet.ShouldProcess($diskPath, 'write Android 10 system and vendor to TF2')) { return }

$stream = [IO.File]::Open($diskPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
$buffer = New-Object byte[] (4MB)
try {
    function Copy-AtOffset([string]$source, [int64]$offset, [int64]$length) {
        $stream.Seek($offset, [IO.SeekOrigin]::Begin) | Out-Null
        $input = [IO.File]::OpenRead($source)
        try {
            $remaining = $length
            while ($remaining -gt 0) {
                $want = [Math]::Min([int64]$buffer.Length, $remaining)
                $read = $input.Read($buffer, 0, [int]$want)
                if ($read -le 0) { throw "Unexpected EOF in $source" }
                $stream.Write($buffer, 0, $read)
                $remaining -= $read
            }
        } finally { $input.Dispose() }
    }
    Copy-AtOffset $systemPath $systemOffset $systemBytes
    Copy-AtOffset $vendorPath $vendorOffset $vendorBytes
    $stream.Flush()
} finally { $stream.Dispose() }

function Hash-Range([int64]$offset, [int64]$length) {
    $s = [IO.File]::Open($diskPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $s.Seek($offset, [IO.SeekOrigin]::Begin) | Out-Null
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $remaining = $length
            while ($remaining -gt 0) {
                $want = [Math]::Min([int64]$buffer.Length, $remaining)
                $read = $s.Read($buffer, 0, [int]$want)
                if ($read -le 0) { throw 'Unexpected EOF while reading physical disk' }
                [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
                $remaining -= $read
            }
            [void]$sha.TransformFinalBlock([byte[]]::new(0), 0, 0)
            return ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLowerInvariant()
        } finally { $sha.Dispose() }
    } finally { $s.Dispose() }
}

$systemExpected = (Get-FileHash -LiteralPath $systemPath -Algorithm SHA256).Hash.ToLowerInvariant()
$vendorExpected = (Get-FileHash -LiteralPath $vendorPath -Algorithm SHA256).Hash.ToLowerInvariant()
$systemActual = Hash-Range $systemOffset $systemBytes
$vendorActual = Hash-Range $vendorOffset $vendorBytes
Write-Host "SYSTEM_EXPECTED=$systemExpected"
Write-Host "SYSTEM_ACTUAL=$systemActual"
Write-Host "VENDOR_EXPECTED=$vendorExpected"
Write-Host "VENDOR_ACTUAL=$vendorActual"
if ($systemExpected -ne $systemActual -or $vendorExpected -ne $vendorActual) { throw 'Readback hash mismatch' }
Write-Host 'TF2_ANDROID10_PREFLIGHT_WRITE_OK'
