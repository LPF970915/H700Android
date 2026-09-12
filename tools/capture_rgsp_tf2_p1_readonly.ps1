[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][int]$DiskNumber,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
$outRoot = [IO.Path]::GetFullPath((Join-Path $root 'out')) + [IO.Path]::DirectorySeparatorChar
if (!$output.StartsWith($outRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $output -eq $outRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)) {
    throw 'Output must be a new directory inside workspace out.'
}
if (Test-Path -LiteralPath $output) { throw 'Output directory already exists.' }
$disk = Get-Disk -Number $DiskNumber
if ($disk.BusType -ne 'USB' -or $disk.Size -ne 125069950976L -or
    $disk.PartitionStyle -ne 'GPT' -or $disk.IsBoot -or $disk.IsSystem -or
    $disk.IsOffline -or $disk.IsReadOnly) {
    throw 'TF2 disk identity gate failed.'
}
$parts = @(Get-Partition -DiskNumber $DiskNumber | Sort-Object PartitionNumber)
$expected = @(
    @(1048576L, 268435456L, '0720745f-bbfb-4940-bef7-8595c6f34f4b'),
    @(269484032L, 8589934592L, '096d7fa1-62e8-c242-9876-cfdd5a92b8eb'),
    @(8859418624L, 2147483648L, '6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8'),
    @(11006902272L, 17179869184L, '734716ed-e7d9-e74f-9b3e-4f1cb8d448ed'),
    @(28186771456L, 96883162624L, '324a1514-de37-6344-8d09-ed5dd8b90da2')
)
if ($parts.Count -ne 5) { throw 'Expected five TF2 partitions.' }
for ($i = 0; $i -lt 5; $i++) {
    if ($parts[$i].PartitionNumber -ne $i + 1 -or
        $parts[$i].Offset -ne $expected[$i][0] -or
        $parts[$i].Size -ne $expected[$i][1] -or
        ([guid]$parts[$i].Guid).ToString() -ne $expected[$i][2]) {
        throw "Partition $($i + 1) identity mismatch."
    }
}
New-Item -ItemType Directory -Path $output | Out-Null
$path = Join-Path $output 'tf2-p1.raw.img'
$offset = 1048576L
$length = 268435456L
$buffer = New-Object byte[] (4MB)
$sha = [Security.Cryptography.SHA256]::Create()
$raw = $null
$dest = $null
try {
    $raw = [IO.File]::Open("\\.\PhysicalDrive$DiskNumber", 'Open', 'Read', 'ReadWrite')
    [void]$raw.Seek($offset, [IO.SeekOrigin]::Begin)
    $dest = [IO.File]::Open($path, 'CreateNew', 'ReadWrite', 'None')
    $left = $length
    while ($left -gt 0) {
        $n = $raw.Read($buffer, 0, [int][Math]::Min($left, $buffer.Length))
        if ($n -le 0) { throw 'Unexpected physical disk EOF.' }
        $dest.Write($buffer, 0, $n)
        [void]$sha.TransformBlock($buffer, 0, $n, $buffer, 0)
        $left -= $n
    }
    $dest.Flush($true)
    $dest.Dispose()
    $dest = $null
    [void]$sha.TransformFinalBlock([byte[]]@(), 0, 0)
    $hash = ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $hash) {
        throw 'Capture readback hash mismatch.'
    }
    @{
        disk_number = $DiskNumber; disk_unique_id = $disk.UniqueId
        source_offset = $offset; bytes = $length; sha256 = $hash
        filesystem = 'FAT32'; device_writes = $false
        captured = (Get-Date).ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'capture.json') -Encoding UTF8
    Write-Host "TF2_P1_READONLY_CAPTURE_OK=$path"
    Write-Host "P1_SHA256=$hash"
} finally {
    if ($dest) { $dest.Dispose() }
    if ($raw) { $raw.Dispose() }
    $sha.Dispose()
}
