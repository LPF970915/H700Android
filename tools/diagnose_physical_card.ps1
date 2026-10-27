#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ImagePath,
    [Parameter(Mandatory)][int]$DiskNumber,
    [Parameter(Mandatory)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$image = Get-Item -LiteralPath $ImagePath
$device = "\\.\PhysicalDrive$DiskNumber"
$source = [IO.File]::Open($image.FullName, 'Open', 'Read', 'Read')
$raw = [IO.FileStream]::new($device, 'Open', 'Read', 'ReadWrite', 65536)
$buffer = [byte[]]::new(4MB)
$comparisons = @()
try {
    foreach ($length in @(1MB, 222298112L)) {
        [void]$source.Seek(0, 'Begin')
        [void]$raw.Seek(0, 'Begin')
        $sourceHash = [Security.Cryptography.IncrementalHash]::CreateHash(
            [Security.Cryptography.HashAlgorithmName]::SHA256)
        $deviceHash = [Security.Cryptography.IncrementalHash]::CreateHash(
            [Security.Cryptography.HashAlgorithmName]::SHA256)
        [long]$done = 0
        while ($done -lt $length) {
            $want = [int][Math]::Min($buffer.Length, $length - $done)
            $read = $source.Read($buffer, 0, $want)
            if ($read -ne $want) { throw "Source read $read/$want" }
            $sourceHash.AppendData($buffer, 0, $read)
            $readDevice = $raw.Read($buffer, 0, $want)
            if ($readDevice -ne $want) { throw "Device read $readDevice/$want" }
            $deviceHash.AppendData($buffer, 0, $readDevice)
            $done += $read
        }
        $sourceSha = [Convert]::ToHexString($sourceHash.GetHashAndReset()).ToLowerInvariant()
        $deviceSha = [Convert]::ToHexString($deviceHash.GetHashAndReset()).ToLowerInvariant()
        $sourceHash.Dispose()
        $deviceHash.Dispose()
        $comparisons += [pscustomobject]@{
            bytes = $length
            image_sha256 = $sourceSha
            device_sha256 = $deviceSha
            match = ($sourceSha -eq $deviceSha)
        }
    }
    [void]$raw.Seek(0, 'Begin')
    $head = [byte[]]::new(512)
    [void]$raw.Read($head, 0, 512)
    [pscustomobject]@{
        completed = (Get-Date -Format o)
        disk = Get-Disk -Number $DiskNumber | Select-Object Number,SerialNumber,Size,IsReadOnly,IsOffline,HealthStatus
        partitions = @(Get-Partition -DiskNumber $DiskNumber | Select-Object PartitionNumber,Size,GptType)
        comparisons = $comparisons
        head_hex = [BitConverter]::ToString($head).Replace('-', '')
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath
}
finally {
    $raw.Dispose()
    $source.Dispose()
}
