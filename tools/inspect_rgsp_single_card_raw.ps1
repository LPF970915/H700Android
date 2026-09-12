[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'rgsp_vendor_io.ps1')
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$out = Join-Path $root ('out/single-card-inspect-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
[void](New-Item -ItemType Directory -Path $out)
Start-Transcript -LiteralPath (Join-Path $out 'inspect.log') -NoClobber | Out-Null
$raw = $null
$exitCode = 1
try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (!([Security.Principal.WindowsPrincipal]::new($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrator token required.'
    }
    $matches = @(Get-Disk | Where-Object {
        $_.FriendlyName -eq 'Generic MassStorageClass' -and
        $_.SerialNumber.Trim() -eq '000000001539' -and
        $_.Size -eq 62239277056L -and $_.BusType -eq 'USB' -and
        !$_.IsBoot -and !$_.IsSystem -and !$_.IsOffline
    })
    if ($matches.Count -ne 1) { throw 'Expected exactly one target card.' }
    $disk = $matches[0]
    $parts = @(Get-Partition -DiskNumber $disk.Number | Sort-Object PartitionNumber)
    Write-RgspNewJson (Join-Path $out 'disk.json') @{
        disk = $disk | Select-Object Number,FriendlyName,SerialNumber,UniqueId,Size,BusType
        partitions = @($parts | Select-Object PartitionNumber,Offset,Size,Guid,GptType,AccessPaths)
        script_sha256 = (Get-FileHash -LiteralPath $PSCommandPath).Hash
        device_writes = $false
    }
    $raw = [IO.File]::Open("\\.\PhysicalDrive$($disk.Number)", 'Open', 'Read', 'ReadWrite')
    $ranges = @(
        @{ Name = 'head-8m.bin'; Offset = 0L; Length = 8MB },
        @{ Name = 'tail-1m.bin'; Offset = $disk.Size - 1MB; Length = 1MB }
    )
    $boot = @($parts | Where-Object {
        $_.PartitionNumber -eq 1 -and $_.Offset -eq 8MB -and $_.Size -eq 64MB
    })
    if ($boot.Count -ne 1) { throw 'Unexpected boot partition geometry.' }
    $ranges += @{ Name = 'boot-p1.img'; Offset = 8MB; Length = 64MB }
    $checks = foreach ($range in $ranges) {
        $path = Join-Path $out $range.Name
        $dest = [IO.File]::Open($path, 'CreateNew', 'ReadWrite', 'None')
        try {
            Copy-RgspRange $raw $dest $range.Offset 0 $range.Length
            $hash = Get-RgspRangeHash $dest 0 $range.Length
            if ((Get-RgspRangeHash $raw $range.Offset $range.Length) -ne $hash) {
                throw 'Two independent reads disagree.'
            }
        } finally { $dest.Dispose() }
        Write-Host "$($range.Name) $hash"
        @{ file = $range.Name; offset = $range.Offset; bytes = $range.Length; sha256 = $hash }
    }
    Write-RgspNewJson (Join-Path $out 'result.json') @{
        status = 'READONLY_CAPTURE_VERIFIED'
        completed = (Get-Date).ToString('o')
        ranges = @($checks)
        device_writes = $false
    }
    $exitCode = 0
} catch {
    Write-RgspNewJson (Join-Path $out 'error.json') @{
        error = ($_ | Out-String); completed = (Get-Date).ToString('o')
    }
    Write-Host ($_ | Out-String)
} finally {
    if ($raw) { $raw.Dispose() }
    Stop-Transcript | Out-Null
}
exit $exitCode
